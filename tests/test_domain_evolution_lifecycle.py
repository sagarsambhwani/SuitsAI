import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from database.postgres.connection import init_db, async_session_factory
from database.postgres.models import (
    Tenant,
    Policy,
    PolicyClause,
    Control,
    RegulatoryObligation,
    ApplicabilityAssessment,
    ComplianceGap,
    RemediationAction,
    ComplianceException,
    ControlTest,
    ComplianceEvidence,
    InternalDocument,
)


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db(recreate=False)


@pytest.mark.asyncio
async def test_scenario_1_regulatory_change_policy_amendment_to_closure():
    """Scenario 1: Regulatory change -> policy amendment required -> approved -> tested -> closed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin", "X-User-ID": "officer-alice"}

        # 1. Create Obligation
        obl_payload = {
            "obligation_code": "OBL-RBI-CYBER-001",
            "obligation_type": "MANDATE",
            "requirement_text": "All banking API keys shall be rotated at least every 90 days.",
            "jurisdiction": "IN",
        }
        r_obl = await client.post("/api/v1/obligations", json=obl_payload, headers=headers)
        assert r_obl.status_code == 200
        obl_id = r_obl.json()["id"]

        # 2. Evaluate Applicability
        app_payload = {
            "obligation_id": obl_id,
            "legal_entity_id": "Commercial Bank",
            "jurisdiction": "IN",
            "rationale": "Commercial bank operates core API interfaces in India.",
        }
        r_app = await client.post("/api/v1/applicability/evaluate", json=app_payload, headers=headers)
        assert r_app.status_code == 200
        assert r_app.json()["status"] == "APPLICABLE"

        # 3. Create Gap
        gap_payload = {
            "obligation_id": obl_id,
            "gap_type": "POLICY_GAP",
            "description": "Internal policy allows 180-day rotation; regulation requires 90-day.",
            "severity": "HIGH",
        }
        r_gap = await client.post("/api/v1/gaps", json=gap_payload, headers=headers)
        assert r_gap.status_code == 200
        gap_id = r_gap.json()["id"]

        # 4. Calculate Risk
        r_risk = await client.post(
            "/api/v1/risks/calculate",
            json={"gap_id": gap_id, "regulatory_severity": "HIGH", "likelihood": "HIGH", "control_effectiveness": "WEAK"},
            headers=headers,
        )
        assert r_risk.status_code == 200
        assert r_risk.json()["materiality"] in ("HIGH", "CRITICAL")

        # 5. Create Remediation Action
        rem_payload = {
            "gap_id": gap_id,
            "action_type": "POLICY_REVISION",
            "title": "Amend Information Security Policy Clause 4.2 to 90-day rotation",
            "description": "Redline clause and deploy to all production API gateways.",
            "priority": "HIGH",
        }
        r_rem = await client.post("/api/v1/remediations", json=rem_payload, headers=headers)
        assert r_rem.status_code == 200
        rem_id = r_rem.json()["id"]

        # 6. Mark Remediation Implemented
        r_close = await client.patch(
            f"/api/v1/remediations/{rem_id}/status",
            json={"status": "CLOSED", "implementation_notes": "Policy amended and authorized by CCO."},
            headers=headers,
        )
        assert r_close.status_code == 200
        assert r_close.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_scenario_2_and_3_procedure_or_system_change_only():
    """Scenarios 2 & 3: Regulatory change requiring procedure/system change without policy redline."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin"}

        # Create Internal Document (SOP / Procedure)
        doc_payload = {
            "document_type": "SOP",
            "doc_code": "SOP-IT-API-01",
            "title": "API Gateway Credential Maintenance Procedure",
        }
        r_doc = await client.post("/api/v1/internal-documents", json=doc_payload, headers=headers)
        assert r_doc.status_code == 200
        assert r_doc.json()["document_type"] == "SOP"

        # Create Impact Assessment with policy_change_required = False
        impact_payload = {
            "obligation_id": "obl-mock-sys-01",
            "impacted_systems": ["API Gateway", "HashiCorp Vault"],
            "policy_change_required": False,
            "procedure_change_required": True,
            "system_change_required": True,
            "impact_level": "MEDIUM",
        }
        r_imp = await client.post("/api/v1/impact-assessments", json=impact_payload, headers=headers)
        assert r_imp.status_code == 200
        assert r_imp.json()["policy_change_required"] is False
        assert r_imp.json()["system_change_required"] is True


@pytest.mark.asyncio
async def test_scenario_5_partially_applicable_subsidiary():
    """Scenario 5: Partial applicability where requirement applies to parent bank but not overseas subsidiary."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin"}

        app_payload = {
            "obligation_id": "obl-mock-retail-01",
            "legal_entity_id": "Overseas Subsidiary LLC",
            "jurisdiction": "GLOBAL",
            "rationale": "Applies to parent bank in domestic jurisdiction, but foreign subsidiary exempted.",
            "status": "PARTIALLY_APPLICABLE",
        }
        r_app = await client.post("/api/v1/applicability/evaluate", json=app_payload, headers=headers)
        assert r_app.status_code == 200
        assert r_app.json()["status"] in ("PARTIALLY_APPLICABLE", "APPLICABLE")


@pytest.mark.asyncio
async def test_scenario_7_control_test_failure_reopens_remediation():
    """Scenario 7: Remediation implemented -> control test fails -> remediation reopened."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin"}

        # 1. Create Control
        ctrl_payload = {
            "control_code": "CTRL-SEC-90D-ROT",
            "name": "Automated 90-Day Key Rotation Daemon",
            "description": "Cron script rotating API tokens automatically.",
            "control_type": "IT",
        }
        r_ctrl = await client.post("/api/v1/controls", json=ctrl_payload, headers=headers)
        assert r_ctrl.status_code == 200
        ctrl_id = r_ctrl.json()["id"]

        # 2. Create Remediation
        r_rem = await client.post(
            "/api/v1/remediations",
            json={"gap_id": "gap-test-01", "action_type": "CONTROL_DEPLOYMENT", "title": "Deploy rotation daemon", "description": "..."},
            headers=headers,
        )
        rem_id = r_rem.json()["id"]

        # 3. Execute Control Test with FAIL result
        test_payload = {
            "control_id": ctrl_id,
            "test_procedure": "Sample 50 production keys and verify age <= 90 days.",
            "result": "FAIL",
            "findings": "3 keys found with age 102 days due to vault timeout.",
            "remediation_id_to_reopen": rem_id,
        }
        r_test = await client.post("/api/v1/control-tests", json=test_payload, headers=headers)
        assert r_test.status_code == 200
        assert r_test.json()["result"] == "FAIL"

        # 4. Verify Remediation was reopened
        r_rems = await client.get("/api/v1/remediations", headers=headers)
        target_rem = next(r for r in r_rems.json() if r["id"] == rem_id)
        assert target_rem["status"] == "REOPENED"


@pytest.mark.asyncio
async def test_scenario_8_exception_and_evidence_upload():
    """Scenario 8: Formal exception requested & approved with compensating controls and evidence upload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin", "X-User-ID": "cco-john"}

        # 1. Request Exception
        exc_payload = {
            "gap_id": "gap-legacy-core-01",
            "reason": "Legacy mainframe cannot rotate keys without scheduled weekend downtime.",
            "compensating_control": "Network mTLS boundary and strict IP whitelisting enforced.",
            "residual_risk": "MEDIUM",
            "expiry_date": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "review_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }
        r_exc = await client.post("/api/v1/exceptions", json=exc_payload, headers=headers)
        assert r_exc.status_code == 200
        exc_id = r_exc.json()["id"]
        assert r_exc.json()["status"] == "REQUESTED"

        # 2. Approve Exception
        r_app = await client.post(f"/api/v1/exceptions/{exc_id}/approve", headers=headers)
        assert r_app.status_code == 200
        assert r_app.json()["status"] == "APPROVED"

        # 3. Upload Immutable Evidence
        ev_payload = {
            "evidence_type": "AUDIT_REPORT",
            "source": "mTLS Configuration Audit Log",
            "description": "Firewall logs verifying IP whitelisting for mainframe.",
            "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "storage_reference": "s3://compliance-platform/evidence/mtls_audit.pdf",
        }
        r_ev = await client.post("/api/v1/evidence", json=ev_payload, headers=headers)
        assert r_ev.status_code == 200
        assert r_ev.json()["verification_status"] == "VERIFIED"


@pytest.mark.asyncio
async def test_scenario_9_historical_as_of_audit_query():
    """Scenario 9: Historical audit asking 'What was effective on date T?'"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Tenant-ID": "tenant-corp-bank", "X-User-Role": "admin"}

        now_str = datetime.utcnow().isoformat()
        r_asof = await client.get(f"/api/v1/compliance/as-of?as_of_date={now_str}", headers=headers)
        assert r_asof.status_code == 200
        data = r_asof.json()
        assert "active_policies_count" in data
        assert "active_controls_count" in data
        assert "active_obligations_count" in data
