import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from services.api.main import app
from services.ingestion.parser import DocumentParser
from services.compliance.verification import IndependentComplianceValidator
from database.postgres.connection import init_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()


def test_adversarial_exception_extraction():
    """Test that regulatory exceptions ('except when Y') are accurately extracted."""
    text = """
    Section 5.2 Customer Verification:
    Regulated entities must maintain video KYC records for a minimum period of 10 years, except when customer is central government entity.
    """
    parsed = DocumentParser.parse_regulatory_text(text, default_code="REG-KYC-01")
    assert len(parsed.extracted_requirements) >= 1
    req = parsed.extracted_requirements[0]
    assert req.obligation_type == "MANDATORY"
    assert len(req.exceptions) >= 1
    assert "central government entity" in req.exceptions[0]


def test_adversarial_negative_requirement_extraction():
    """Test that negative requirements ('must not perform X') are classified as PROHIBITED."""
    text = """
    Section 3.1 Prohibited Data Storage:
    Regulated entities shall not store raw customer card CVV numbers under any circumstances.
    """
    parsed = DocumentParser.parse_regulatory_text(text, default_code="REG-CARD-01")
    assert len(parsed.extracted_requirements) >= 1
    req = parsed.extracted_requirements[0]
    assert req.obligation_type == "PROHIBITED"


def test_8_gate_verification_scorecard_positive_and_failure():
    now = datetime.utcnow()
    # Positive full scorecard
    scorecard = IndependentComplianceValidator.evaluate_all_gates(
        document_sha256="abc123sha",
        expected_sha256="abc123sha",
        raw_document_text="Regulated entities shall rotate keys every 90 days.",
        publication_date=now,
        effective_date=now,
        superseded_date=None,
        regulation_jurisdiction="IN",
        policy_jurisdiction="IN",
        regulation_applies_to=["Commercial Banks"],
        tenant_entity_type="Commercial Banks",
        all_requirements=[{"req_code": "REQ-01", "obligation_text": "rotate keys every 90 days", "exceptions": []}],
        proposed_amendments=[{
            "clause_number": "4.2",
            "proposed_text": "Rotate keys every 90 days.",
            "justification": "Aligned with REQ-01",
            "citations": [{"quote": "rotate keys every 90 days", "page": 1, "doc": "REG-01"}],
        }],
        citations=[{"quote": "rotate keys every 90 days", "page": 1, "claim": "key rotation"}],
    )

    assert scorecard.overall_passed is True
    assert scorecard.passed_gates_count == 8
    assert scorecard.gates["evidence_gate"].passed is True
    assert scorecard.gates["jurisdiction_gate"].passed is True
    assert scorecard.gates["citation_gate"].passed is True


@pytest.mark.asyncio
async def test_end_to_end_replay_and_tenant_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Ingest regulation under Tenant A
        reg_res = await ac.post(
            "/api/v1/regulations/ingest",
            headers={"X-Tenant-ID": "BANK-TENANT-A"},
            json={
                "code": "REG-REPLAY-01",
                "title": "API Security Directive",
                "regulator_name": "Central Bank",
                "jurisdiction": "IN",
                "raw_text": "Section 1.1: Regulated entities shall rotate keys every 90 days.",
            },
        )
        assert reg_res.status_code == 200
        reg_data = reg_res.json()

        # 2. Run Impact Analysis under Tenant A
        analyze_res = await ac.post(
            "/api/v1/compliance/analyze",
            headers={"X-Tenant-ID": "BANK-TENANT-A"},
            json={
                "regulation_id": reg_data["id"],
                "async_mode": False,
                "mode": "standard",
            },
        )
        assert analyze_res.status_code == 200
        asmt_data = analyze_res.json()
        run_id = asmt_data["run_id"]
        assert run_id is not None

        # 3. Auditor Replay Facility under Tenant A (Should succeed)
        replay_res = await ac.get(
            f"/api/v1/compliance/runs/{run_id}/replay",
            headers={"X-Tenant-ID": "BANK-TENANT-A"},
        )
        assert replay_res.status_code == 200
        replay_data = replay_res.json()
        assert replay_data["run_id"] == run_id
        assert replay_data["model_version"] is not None
        assert "evidence_gate" in replay_data["verification_scorecard"]["gates"]

        # 4. Multi-Tenant Penetration Attempt: Tenant B tries to replay Tenant A's run
        cross_tenant_res = await ac.get(
            f"/api/v1/compliance/runs/{run_id}/replay",
            headers={"X-Tenant-ID": "BANK-TENANT-B"},
        )
        assert cross_tenant_res.status_code == 404  # Must strictly refuse / isolate

        # 5. Capture Reviewer Decision & Feedback
        if asmt_data["changes"]:
            change_id = asmt_data["changes"][0]["id"]
            feedback_res = await ac.post(
                "/api/v1/compliance/feedback",
                headers={"X-Tenant-ID": "BANK-TENANT-A"},
                json={
                    "policy_change_id": change_id,
                    "decision": "REJECT",
                    "rejection_reason_category": "SCOPE_MISMATCH",
                    "reviewer_comments": "This circular only applies to retail domestic branches.",
                },
            )
            assert feedback_res.status_code == 200
            assert feedback_res.json()["status"] == "recorded"
