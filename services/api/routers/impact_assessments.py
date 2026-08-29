from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ImpactAssessment
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/impact-assessments", tags=["Impact Assessments"])


class ImpactAssessmentCreate(BaseModel):
    obligation_id: str
    applicability_assessment_id: Optional[str] = None
    impacted_processes: List[str] = Field(default_factory=list)
    impacted_business_units: List[str] = Field(default_factory=list)
    impacted_systems: List[str] = Field(default_factory=list)
    impacted_controls: List[str] = Field(default_factory=list)
    impacted_documents: List[str] = Field(default_factory=list)
    current_state: Optional[str] = None
    target_state: Optional[str] = None
    gap_summary: Optional[str] = None
    policy_change_required: bool = False
    procedure_change_required: bool = False
    system_change_required: bool = False
    control_change_required: bool = False
    training_change_required: bool = False
    impact_level: str = "MEDIUM"


class ImpactAssessmentResponse(BaseModel):
    id: str
    obligation_id: str
    tenant_id: str
    impacted_processes: List[str]
    impacted_business_units: List[str]
    impacted_systems: List[str]
    policy_change_required: bool
    procedure_change_required: bool
    system_change_required: bool
    control_change_required: bool
    training_change_required: bool
    impact_level: str
    assessment_status: str
    approved_by: Optional[str] = None
    created_at: datetime


@router.get("", response_model=List[ImpactAssessmentResponse])
async def list_impact_assessments(
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ImpactAssessment).where(ImpactAssessment.tenant_id == ctx.tenant_id)
    result = await db.execute(query)
    assessments = result.scalars().all()
    return [
        ImpactAssessmentResponse(
            id=a.id,
            obligation_id=a.obligation_id,
            tenant_id=a.tenant_id,
            impacted_processes=a.impacted_processes or [],
            impacted_business_units=a.impacted_business_units or [],
            impacted_systems=a.impacted_systems or [],
            policy_change_required=a.policy_change_required,
            procedure_change_required=a.procedure_change_required,
            system_change_required=a.system_change_required,
            control_change_required=a.control_change_required,
            training_change_required=a.training_change_required,
            impact_level=a.impact_level,
            assessment_status=a.assessment_status,
            approved_by=a.approved_by,
            created_at=a.created_at,
        )
        for a in assessments
    ]


@router.post("", response_model=ImpactAssessmentResponse)
async def create_impact_assessment(
    payload: ImpactAssessmentCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    assessment = ImpactAssessment(
        obligation_id=payload.obligation_id,
        tenant_id=ctx.tenant_id,
        applicability_assessment_id=payload.applicability_assessment_id,
        impacted_processes=payload.impacted_processes,
        impacted_business_units=payload.impacted_business_units,
        impacted_systems=payload.impacted_systems,
        impacted_controls=payload.impacted_controls,
        impacted_documents=payload.impacted_documents,
        current_state=payload.current_state,
        target_state=payload.target_state,
        gap_summary=payload.gap_summary,
        policy_change_required=payload.policy_change_required,
        procedure_change_required=payload.procedure_change_required,
        system_change_required=payload.system_change_required,
        control_change_required=payload.control_change_required,
        training_change_required=payload.training_change_required,
        impact_level=payload.impact_level,
        assessment_status="AI_ASSESSED",
        assessed_by=ctx.user_id,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return ImpactAssessmentResponse(
        id=assessment.id,
        obligation_id=assessment.obligation_id,
        tenant_id=assessment.tenant_id,
        impacted_processes=assessment.impacted_processes or [],
        impacted_business_units=assessment.impacted_business_units or [],
        impacted_systems=assessment.impacted_systems or [],
        policy_change_required=assessment.policy_change_required,
        procedure_change_required=assessment.procedure_change_required,
        system_change_required=assessment.system_change_required,
        control_change_required=assessment.control_change_required,
        training_change_required=assessment.training_change_required,
        impact_level=assessment.impact_level,
        assessment_status=assessment.assessment_status,
        approved_by=assessment.approved_by,
        created_at=assessment.created_at,
    )
