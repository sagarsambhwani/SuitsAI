import pytest
from sqlalchemy import select
from datetime import datetime

from database.postgres.models import (
    Tenant,
    Policy,
    PolicyClause,
    Control,
    Regulation,
    DocumentVersion,
    RequirementVersion,
    RegulatorySource,
    AuditEvent,
)


@pytest.mark.asyncio
async def test_tenant_and_policy_creation(db_session):
    # 1. Create Tenant
    tenant = Tenant(
        id="BANK-001",
        name="Apex Commercial Bank",
        slug="BANK-001",
        tier="enterprise",
    )
    db_session.add(tenant)
    await db_session.commit()

    # 2. Create Policy with Clauses and Controls
    policy = Policy(
        id="POL-001",
        tenant_id=tenant.id,
        policy_code="POL-AML-001",
        title="Anti-Money Laundering & KYC Policy",
        category="AML",
        jurisdiction="IN",
    )
    db_session.add(policy)

    clause = PolicyClause(
        policy_id=policy.id,
        tenant_id=tenant.id,
        clause_number="Clause 3.1",
        text="Customer due diligence shall be performed prior to account opening.",
    )
    db_session.add(clause)

    control = Control(
        policy_id=policy.id,
        tenant_id=tenant.id,
        control_code="CTL-AML-01",
        name="Automated KYC Sanction Screening",
        description="Continuous sanction checks against global watchlists.",
    )
    db_session.add(control)
    await db_session.commit()

    # Query back
    res = await db_session.execute(select(Policy).where(Policy.tenant_id == tenant.id))
    retrieved_policy = res.scalar_one()

    assert retrieved_policy.policy_code == "POL-AML-001"
    assert retrieved_policy.title == "Anti-Money Laundering & KYC Policy"


@pytest.mark.asyncio
async def test_regulation_and_requirements(db_session):
    source = RegulatorySource(
        name="Reserve Bank of India",
        acronym="RBI",
        jurisdiction="IN",
    )
    db_session.add(source)
    await db_session.flush()

    regulation = Regulation(
        source_id=source.id,
        code="RBI/2026/01",
        title="Master Direction on Cybersecurity Controls in Banks",
        doc_type="Master Direction",
        jurisdiction="IN",
    )
    db_session.add(regulation)
    await db_session.flush()

    doc_version = DocumentVersion(
        regulation_id=regulation.id,
        version_number="1.0.0",
        sha256_hash="abc1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcd",
        storage_uri="s3://lake/RBI/cyber.pdf",
        publication_date=datetime.utcnow(),
        effective_date=datetime.utcnow(),
        raw_content="Banks shall establish a 24x7 SOC.",
    )
    db_session.add(doc_version)
    await db_session.flush()

    requirement = RequirementVersion(
        document_version_id=doc_version.id,
        req_code="REQ-SEC-01",
        obligation_text="Banks shall establish a 24x7 Security Operations Centre (SOC).",
        obligation_type="MANDATORY",
        risk_category="Cybersecurity",
    )
    db_session.add(requirement)
    await db_session.commit()

    res = await db_session.execute(select(RequirementVersion).where(RequirementVersion.document_version_id == doc_version.id))
    retrieved_reqs = res.scalars().all()

    assert len(retrieved_reqs) == 1
    assert retrieved_reqs[0].obligation_type == "MANDATORY"
