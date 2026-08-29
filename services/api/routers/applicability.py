from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ApplicabilityAssessment, RegulatoryObligation
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions
from services.compliance.rules_engine import ComplianceRulesEngine

router = APIRouter(prefix="/applicability", tags=["Applicability Assessments"])


class ApplicabilityCreate(BaseModel):
    obligation_id: str
    legal_entity_id: Optional[str] = "Commercial Banking Group"
    jurisdiction: str = "GLOBAL"
    product_id: Optional[str] = None
    business_unit_id: Optional[str] = "Compliance"
    status: str = "APPLICABLE"  # APPLICABLE, PARTIALLY_APPLICABLE, NOT_APPLICABLE, UNDER_REVIEW
    rationale: str


class ApplicabilityApproveRequest(BaseModel):
    approved: bool
    rationale: Optional[str] = None


class ApplicabilityResponse(BaseModel):
    id: str
    obligation_id: str
    tenant_id: str
    status: str
    rationale: str
    confidence: float
    approval_required: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime


@router.get("", response_model=List[ApplicabilityResponse])
async def list_applicability_assessments(
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ApplicabilityAssessment).where(ApplicabilityAssessment.tenant_id == ctx.tenant_id)
    result = await db.execute(query)
    assessments = result.scalars().all()
    return [
        ApplicabilityResponse(
            id=a.id,
            obligation_id=a.obligation_id,
            tenant_id=a.tenant_id,
            status=a.status,
            rationale=a.rationale,
            confidence=a.confidence,
            approval_required=a.approval_required,
            approved_by=a.approved_by,
            approved_at=a.approved_at,
            created_at=a.created_at,
        )
        for a in assessments
    ]


@router.post("/evaluate", response_model=ApplicabilityResponse)
async def evaluate_applicability(
    payload: ApplicabilityCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    # Fetch obligation
    query = select(RegulatoryObligation).where(RegulatoryObligation.id == payload.obligation_id)
    result = await db.execute(query)
    obl = result.scalar_one_or_none()
    
    app_res = ComplianceRulesEngine.evaluate_applicability(
        obligation_applies_to=["Commercial Banks", "Digital Lending Entities"],
        obligation_jurisdiction=payload.jurisdiction,
        tenant_entity_type=payload.legal_entity_id or "Commercial Bank",
        tenant_jurisdiction=payload.jurisdiction or "GLOBAL",
    )

    assessment = ApplicabilityAssessment(
        obligation_id=payload.obligation_id,
        tenant_id=ctx.tenant_id,
        legal_entity_id=payload.legal_entity_id,
        jurisdiction=payload.jurisdiction,
        product_id=payload.product_id,
        business_unit_id=payload.business_unit_id,
        status=app_res.status,
        rationale=app_res.rationale,
        confidence=app_res.confidence,
        assessed_by=ctx.user_id,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return ApplicabilityResponse(
        id=assessment.id,
        obligation_id=assessment.obligation_id,
        tenant_id=assessment.tenant_id,
        status=assessment.status,
        rationale=assessment.rationale,
        confidence=assessment.confidence,
        approval_required=assessment.approval_required,
        approved_by=assessment.approved_by,
        approved_at=assessment.approved_at,
        created_at=assessment.created_at,
    )


@router.post("/{id}/approve", response_model=ApplicabilityResponse)
async def approve_applicability(
    id: str,
    payload: ApplicabilityApproveRequest,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(require_permissions(["policy:publish"])),
):
    query = select(ApplicabilityAssessment).where(
        ApplicabilityAssessment.id == id,
        ApplicabilityAssessment.tenant_id == ctx.tenant_id,
    )
    result = await db.execute(query)
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Applicability assessment not found")

    assessment.approved_by = ctx.user_id
    assessment.approved_at = datetime.utcnow()
    if not payload.approved:
        assessment.status = "NOT_APPLICABLE"
        if payload.rationale:
            assessment.rationale += f" [Rejected by {ctx.user_id}: {payload.rationale}]"

    await db.commit()
    await db.refresh(assessment)

    return ApplicabilityResponse(
        id=assessment.id,
        obligation_id=assessment.obligation_id,
        tenant_id=assessment.tenant_id,
        status=assessment.status,
        rationale=assessment.rationale,
        confidence=assessment.confidence,
        approval_required=assessment.approval_required,
        approved_by=assessment.approved_by,
        approved_at=assessment.approved_at,
        created_at=assessment.created_at,
    )
