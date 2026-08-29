from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import RiskAssessment, ComplianceGap
from services.api.dependencies import get_tenant_context, TenantContext
from services.compliance.rules_engine import ComplianceRulesEngine

router = APIRouter(prefix="/risks", tags=["Risk & Materiality"])


class RiskAssessmentCreate(BaseModel):
    gap_id: str
    regulatory_severity: str = "HIGH"
    customer_impact: str = "MEDIUM"
    financial_impact: str = "HIGH"
    operational_impact: str = "MEDIUM"
    likelihood: str = "MEDIUM"
    control_effectiveness: str = "WEAK"


class RiskAssessmentResponse(BaseModel):
    id: str
    gap_id: str
    tenant_id: str
    regulatory_severity: str
    inherent_risk: str
    control_effectiveness: str
    residual_risk: str
    materiality: str
    rationale: str
    created_at: datetime


@router.get("", response_model=List[RiskAssessmentResponse])
async def list_risk_assessments(
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(RiskAssessment).where(RiskAssessment.tenant_id == ctx.tenant_id)
    result = await db.execute(query)
    assessments = result.scalars().all()
    return [
        RiskAssessmentResponse(
            id=r.id,
            gap_id=r.gap_id,
            tenant_id=r.tenant_id,
            regulatory_severity=r.regulatory_severity,
            inherent_risk=r.inherent_risk,
            control_effectiveness=r.control_effectiveness,
            residual_risk=r.residual_risk,
            materiality=r.materiality,
            rationale=r.rationale,
            created_at=r.created_at,
        )
        for r in assessments
    ]


@router.post("/calculate", response_model=RiskAssessmentResponse)
async def calculate_and_save_risk(
    payload: RiskAssessmentCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    risk_res = ComplianceRulesEngine.calculate_risk_and_materiality(
        regulatory_severity=payload.regulatory_severity,
        customer_impact=payload.customer_impact,
        financial_impact=payload.financial_impact,
        operational_impact=payload.operational_impact,
        likelihood=payload.likelihood,
        control_effectiveness=payload.control_effectiveness,
    )

    assessment = RiskAssessment(
        gap_id=payload.gap_id,
        tenant_id=ctx.tenant_id,
        regulatory_severity=risk_res.regulatory_severity,
        customer_impact=risk_res.customer_impact,
        financial_impact=risk_res.financial_impact,
        operational_impact=risk_res.operational_impact,
        likelihood=risk_res.likelihood,
        inherent_risk=risk_res.inherent_risk,
        control_effectiveness=risk_res.control_effectiveness,
        residual_risk=risk_res.residual_risk,
        materiality=risk_res.materiality,
        formula_version=risk_res.formula_version,
        calculation_inputs=risk_res.calculation_inputs,
        rationale=risk_res.rationale,
        assessed_by=ctx.user_id,
    )
    db.add(assessment)
    await db.commit()
    await db.refresh(assessment)

    return RiskAssessmentResponse(
        id=assessment.id,
        gap_id=assessment.gap_id,
        tenant_id=assessment.tenant_id,
        regulatory_severity=assessment.regulatory_severity,
        inherent_risk=assessment.inherent_risk,
        control_effectiveness=assessment.control_effectiveness,
        residual_risk=assessment.residual_risk,
        materiality=assessment.materiality,
        rationale=assessment.rationale,
        created_at=assessment.created_at,
    )
