from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ComplianceEvidence
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/evidence", tags=["Compliance Evidence"])


class EvidenceCreate(BaseModel):
    evidence_type: str = "SYSTEM_LOG"  # SYSTEM_LOG, AUDIT_REPORT, SCREENSHOT, POLICY_DOC, TRAINING_RECORD
    source: str
    description: str
    content_hash: str  # Immutable SHA-256
    storage_reference: str  # s3://compliance-platform/evidence/...
    control_id: Optional[str] = None
    remediation_id: Optional[str] = None
    test_id: Optional[str] = None


class EvidenceResponse(BaseModel):
    id: str
    tenant_id: str
    evidence_type: str
    source: str
    description: str
    content_hash: str
    storage_reference: str
    control_id: Optional[str] = None
    remediation_id: Optional[str] = None
    test_id: Optional[str] = None
    verification_status: str
    collected_at: datetime
    created_at: datetime


@router.get("", response_model=List[EvidenceResponse])
async def list_evidence(
    control_id: Optional[str] = None,
    remediation_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ComplianceEvidence).where(ComplianceEvidence.tenant_id == ctx.tenant_id)
    if control_id:
        query = query.where(ComplianceEvidence.control_id == control_id)
    if remediation_id:
        query = query.where(ComplianceEvidence.remediation_id == remediation_id)
    result = await db.execute(query)
    evidences = result.scalars().all()
    return [
        EvidenceResponse(
            id=e.id,
            tenant_id=e.tenant_id,
            evidence_type=e.evidence_type,
            source=e.source,
            description=e.description,
            content_hash=e.content_hash,
            storage_reference=e.storage_reference,
            control_id=e.control_id,
            remediation_id=e.remediation_id,
            test_id=e.test_id,
            verification_status=e.verification_status,
            collected_at=e.collected_at,
            created_at=e.created_at,
        )
        for e in evidences
    ]


@router.post("", response_model=EvidenceResponse)
async def upload_evidence_record(
    payload: EvidenceCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    evidence = ComplianceEvidence(
        tenant_id=ctx.tenant_id,
        evidence_type=payload.evidence_type,
        source=payload.source,
        description=payload.description,
        content_hash=payload.content_hash,
        storage_reference=payload.storage_reference,
        control_id=payload.control_id,
        remediation_id=payload.remediation_id,
        test_id=payload.test_id,
        collected_by=ctx.user_id,
        verification_status="VERIFIED",
        verified_by=ctx.user_id,
        verified_at=datetime.utcnow(),
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)

    return EvidenceResponse(
        id=evidence.id,
        tenant_id=evidence.tenant_id,
        evidence_type=evidence.evidence_type,
        source=evidence.source,
        description=evidence.description,
        content_hash=evidence.content_hash,
        storage_reference=evidence.storage_reference,
        control_id=evidence.control_id,
        remediation_id=evidence.remediation_id,
        test_id=evidence.test_id,
        verification_status=evidence.verification_status,
        collected_at=evidence.collected_at,
        created_at=evidence.created_at,
    )
