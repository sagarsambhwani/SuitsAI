import pytest
from httpx import AsyncClient, ASGITransport
from services.api.main import app
from database.postgres.connection import init_db
from services.compliance.evaluation import GoldenComplianceEvaluator
from services.ingestion.worker import get_job_manager, IngestionJobStatus


@pytest.fixture(autouse=True)
async def setup_test_db():
    await init_db()


def test_golden_compliance_benchmark_metrics():
    """Verifies that all 5 golden ground-truth compliance scenarios pass with 100% precision."""
    report = GoldenComplianceEvaluator.evaluate_benchmark()
    assert report.total_test_cases >= 5
    assert report.passed_test_cases == report.total_test_cases
    assert report.overall_benchmark_passed is True
    assert report.faithfulness_score == 1.0


@pytest.mark.asyncio
async def test_async_ingestion_job_lifecycle():
    """Tests the asynchronous distributed document ingestion worker pipeline."""
    job_mgr = get_job_manager()
    job = job_mgr.create_job(
        tenant_id="BANK-TEST-001",
        filename="async_circular.txt",
        code="REG-ASYNC-01",
        regulator="RBI",
        jurisdiction="IN",
    )
    assert job.status == IngestionJobStatus.QUEUED

    content = b"""Section 1.1 Mandatory Reporting:
    All cyber security incidents must be reported to the central authority within 6 hours.
    """
    await job_mgr.execute_ingestion_pipeline(job.job_id, content)

    updated_job = job_mgr.get_job(job.job_id)
    assert updated_job is not None
    assert updated_job.status == IngestionJobStatus.COMPLETED
    assert updated_job.progress_percentage == 100
    assert updated_job.total_sections >= 1
    assert updated_job.total_chunks >= 1
    assert updated_job.sha256_hash is not None


@pytest.mark.asyncio
async def test_maker_checker_4_eyes_workflow_and_rbac():
    """Tests the 4-Eyes Principle: Maker submits, Checker authorizes, prevents self-approval."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Ingest regulation
        reg_res = await ac.post(
            "/api/v1/regulations/ingest",
            headers={"X-Tenant-ID": "BANK-4EYES-001", "X-Role": "compliance_maker"},
            json={
                "code": "REG-4EYES-01",
                "title": "Dual Control Test Directive",
                "regulator_name": "Reserve Bank of India",
                "jurisdiction": "IN",
                "raw_text": "Section 1.1: All API tokens shall be rotated every 90 days.",
            },
        )
        assert reg_res.status_code == 200
        reg_data = reg_res.json()

        # 2. Run Impact Analysis
        impact_res = await ac.post(
            "/api/v1/compliance/analyze",
            headers={"X-Tenant-ID": "BANK-4EYES-001", "X-Role": "compliance_maker"},
            json={"regulation_id": reg_data["id"], "async_mode": False},
        )
        assert impact_res.status_code == 200
        impact_data = impact_res.json()
        assert len(impact_data["changes"]) >= 1
        change_id = impact_data["changes"][0]["id"]

        # 3. Step 1 of 4-Eyes: Maker submits proposal
        maker_res = await ac.post(
            f"/api/v1/approvals/{change_id}/maker-submit",
            headers={
                "X-Tenant-ID": "BANK-4EYES-001",
                "X-User-ID": "MAKER-ALICE-01",
                "X-Role": "compliance_maker",
            },
            json={"rationale": "Verified against Section 1.1; 90-day rotation requirement."},
        )
        assert maker_res.status_code == 200
        maker_data = maker_res.json()
        assert maker_data["maker_checker_status"] == "MAKER_SUBMITTED"
        assert maker_data["maker_id"] == "MAKER-ALICE-01"

        # 4. Self-approval violation test (Maker cannot be Checker)
        self_check_res = await ac.post(
            f"/api/v1/approvals/{change_id}/checker-decision",
            headers={
                "X-Tenant-ID": "BANK-4EYES-001",
                "X-User-ID": "MAKER-ALICE-01",
                "X-Role": "compliance_checker",
            },
            json={"decision": "APPROVE", "checker_comments": "Attempting self-signoff."},
        )
        assert self_check_res.status_code == 403
        assert "4-Eyes Principle Violation" in self_check_res.json()["detail"]

        # 5. Legitimate Checker authorizes change
        checker_res = await ac.post(
            f"/api/v1/approvals/{change_id}/checker-decision",
            headers={
                "X-Tenant-ID": "BANK-4EYES-001",
                "X-User-ID": "CHECKER-BOB-CCO",
                "X-Role": "compliance_checker",
            },
            json={"decision": "APPROVE", "checker_comments": "Authorized and confirmed by Chief Compliance Officer."},
        )
        assert checker_res.status_code == 200
        checker_data = checker_res.json()
        assert checker_data["maker_checker_status"] == "CHECKER_APPROVED"
        assert checker_data["checker_id"] == "CHECKER-BOB-CCO"
        assert checker_data["digital_signature_hash"] is not None
        assert checker_data["published_policy_version"] is not None


@pytest.mark.asyncio
async def test_benchmark_api_endpoint():
    """Tests the benchmark evaluation API endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/v1/compliance/evaluate-benchmark",
            headers={"X-Tenant-ID": "BANK-BENCH-001", "X-Role": "auditor"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_benchmark_passed"] is True
        assert data["faithfulness_score"] == 1.0
        assert data["total_test_cases"] >= 5
