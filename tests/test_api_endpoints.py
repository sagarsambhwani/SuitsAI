import pytest
from httpx import AsyncClient, ASGITransport
from services.api.main import app
from database.postgres.connection import init_db


@pytest.fixture(autouse=True)
async def setup_api_db():
    await init_db()


@pytest.mark.asyncio
async def test_api_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "SuitsAI" in data["app_name"]


@pytest.mark.asyncio
async def test_auth_and_me_endpoints():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "officer@bank.com",
            "password": "secretPassword123!",
            "tenant_slug": "BANK-GLOBAL-001",
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert token_data["role"] == "compliance_officer"

        me_res = await ac.get("/api/v1/auth/me", headers={"X-Tenant-ID": "BANK-GLOBAL-001"})
        assert me_res.status_code == 200
        profile = me_res.json()
        assert profile["tenant_id"] == "BANK-GLOBAL-001"


@pytest.mark.asyncio
async def test_regulation_ingest_and_policy_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create Policy
        pol_res = await ac.post(
            "/api/v1/policies",
            headers={"X-Tenant-ID": "BANK-GLOBAL-001"},
            json={
                "policy_code": "POL-INF-001",
                "title": "Information Security Policy",
                "category": "Cybersecurity",
                "jurisdiction": "IN",
                "owner_department": "IT Ops",
                "clauses": [
                    {
                        "clause_number": "Clause 4.2",
                        "title": "Key Rotation",
                        "text": "Rotate keys every 180 days.",
                    }
                ],
                "controls": [],
            },
        )
        assert pol_res.status_code == 200
        pol_data = pol_res.json()
        assert pol_data["policy_code"] == "POL-INF-001"

        # 2. Ingest Regulation
        reg_res = await ac.post(
            "/api/v1/regulations/ingest",
            headers={"X-Tenant-ID": "BANK-GLOBAL-001"},
            json={
                "code": "RBI/2026/04",
                "title": "Digital Lending Security Directions",
                "regulator_name": "Reserve Bank of India",
                "regulator_acronym": "RBI",
                "jurisdiction": "IN",
                "doc_type": "Circular",
                "raw_text": "Section 4.1 Key Lifecycle: Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days.",
            },
        )
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        assert reg_data["code"] == "RBI/2026/04"

        # 3. Analyze Compliance Impact
        analyze_res = await ac.post(
            "/api/v1/compliance/analyze",
            headers={"X-Tenant-ID": "BANK-GLOBAL-001"},
            json={
                "regulation_id": reg_data["id"],
                "async_mode": False,
            },
        )
        assert analyze_res.status_code == 200
        asmt_data = analyze_res.json()
        assert asmt_data["status"] in ("COMPLETED", "GATES_FAILED")
        assert len(asmt_data["changes"]) >= 1

        # 4. Human Approval Gateway Decision
        change_id = asmt_data["changes"][0]["id"]
        if change_id:
            appr_res = await ac.post(
                f"/api/v1/approvals/{change_id}/decision",
                headers={"X-Tenant-ID": "BANK-GLOBAL-001"},
                json={
                    "action": "APPROVE",
                    "comments": "Verified and approved.",
                },
            )
            assert appr_res.status_code == 200
            appr_data = appr_res.json()
            assert appr_data["status"] == "APPROVED"
            assert appr_data["published_policy_version"] is not None
