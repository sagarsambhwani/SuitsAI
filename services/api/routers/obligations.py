from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import RegulatoryObligation, RegulatoryProvision
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/obligations", tags=["Regulatory Obligations"])


class ObligationCreate(BaseModel):
    provision_id: Optional[str] = None
    obligation_code: str
    obligation_type: str = "MANDATE"
    requirement_text: str
    normalized_requirement: Optional[str] = None
    mandatory_action: Optional[str] = None
    subject: str = "Regulated Entity"
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    thresholds: List[str] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    jurisdiction: str = "GLOBAL"


class ObligationResponse(BaseModel):
    id: str
    provision_id: Optional[str] = None
    obligation_code: str
    obligation_type: str
    requirement_text: str
    normalized_requirement: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    thresholds: List[str] = Field(default_factory=list)
    deadlines: List[str] = Field(default_factory=list)
    jurisdiction: str
    status: str
    created_at: datetime


@router.get("", response_model=List[ObligationResponse])
async def list_obligations(
    jurisdiction: Optional[str] = None,
    obligation_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(RegulatoryObligation)
    if jurisdiction and jurisdiction != "GLOBAL":
        query = query.where(RegulatoryObligation.jurisdiction.in_([jurisdiction, "GLOBAL"]))
    if obligation_type:
        query = query.where(RegulatoryObligation.obligation_type == obligation_type)
    
    result = await db.execute(query)
    obligations = result.scalars().all()
    return [
        ObligationResponse(
            id=o.id,
            provision_id=o.provision_id,
            obligation_code=o.obligation_code,
            obligation_type=o.obligation_type,
            requirement_text=o.requirement_text,
            normalized_requirement=o.normalized_requirement,
            conditions=o.conditions or [],
            exceptions=o.exceptions or [],
            thresholds=o.thresholds or [],
            deadlines=o.deadlines or [],
            jurisdiction=o.jurisdiction,
            status=o.status,
            created_at=o.created_at,
        )
        for o in obligations
    ]


@router.post("", response_model=ObligationResponse)
async def create_obligation(
    payload: ObligationCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(require_permissions(["policy:write"])),
):
    obl = RegulatoryObligation(
        provision_id=payload.provision_id,
        obligation_code=payload.obligation_code,
        obligation_type=payload.obligation_type,
        requirement_text=payload.requirement_text,
        normalized_requirement=payload.normalized_requirement or payload.requirement_text,
        mandatory_action=payload.mandatory_action,
        subject=payload.subject,
        conditions=payload.conditions,
        exceptions=payload.exceptions,
        thresholds=payload.thresholds,
        deadlines=payload.deadlines,
        jurisdiction=payload.jurisdiction,
    )
    db.add(obl)
    await db.commit()
    await db.refresh(obl)
    return ObligationResponse(
        id=obl.id,
        provision_id=obl.provision_id,
        obligation_code=obl.obligation_code,
        obligation_type=obl.obligation_type,
        requirement_text=obl.requirement_text,
        normalized_requirement=obl.normalized_requirement,
        conditions=obl.conditions or [],
        exceptions=obl.exceptions or [],
        thresholds=obl.thresholds or [],
        deadlines=obl.deadlines or [],
        jurisdiction=obl.jurisdiction,
        status=obl.status,
        created_at=obl.created_at,
    )


@router.get("/{id}", response_model=ObligationResponse)
async def get_obligation(
    id: str,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(RegulatoryObligation).where(RegulatoryObligation.id == id)
    result = await db.execute(query)
    obl = result.scalar_one_or_none()
    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return ObligationResponse(
        id=obl.id,
        provision_id=obl.provision_id,
        obligation_code=obl.obligation_code,
        obligation_type=obl.obligation_type,
        requirement_text=obl.requirement_text,
        normalized_requirement=obl.normalized_requirement,
        conditions=obl.conditions or [],
        exceptions=obl.exceptions or [],
        thresholds=obl.thresholds or [],
        deadlines=obl.deadlines or [],
        jurisdiction=obl.jurisdiction,
        status=obl.status,
        created_at=obl.created_at,
    )
