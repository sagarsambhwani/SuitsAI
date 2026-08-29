from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import Control, Policy
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/controls", tags=["Controls"])


class ControlCreate(BaseModel):
    control_code: str
    name: str
    description: str
    control_type: str = "REGULATORY"
    execution_type: str = "AUTOMATED"
    frequency: str = "CONTINUOUS"
    preventive_or_detective: str = "PREVENTIVE"
    business_unit_id: Optional[str] = "Information Security"
    process_id: Optional[str] = None
    system_id: Optional[str] = None
    test_procedure: Optional[str] = None
    evidence_requirements: Optional[str] = None


class ControlResponse(BaseModel):
    id: str
    control_code: str
    name: str
    description: str
    control_type: str
    execution_type: str
    frequency: str
    preventive_or_detective: str
    effectiveness_status: str
    status: str
    last_tested_at: Optional[datetime] = None
    created_at: datetime


@router.get("", response_model=List[ControlResponse])
async def list_controls(
    control_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(Control).where(Control.tenant_id == ctx.tenant_id)
    if control_type:
        query = query.where(Control.control_type == control_type)
    result = await db.execute(query)
    controls = result.scalars().all()
    return [
        ControlResponse(
            id=c.id,
            control_code=c.control_code,
            name=c.name,
            description=c.description,
            control_type=c.control_type,
            execution_type=c.execution_type,
            frequency=c.frequency,
            preventive_or_detective=c.preventive_or_detective,
            effectiveness_status=c.effectiveness_status,
            status=c.status,
            last_tested_at=c.last_tested_at,
            created_at=c.created_at,
        )
        for c in controls
    ]


@router.post("", response_model=ControlResponse)
async def create_control(
    payload: ControlCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(require_permissions(["policy:write"])),
):
    # Ensure a valid policy_id exists for the tenant
    pol_q = select(Policy).where(Policy.tenant_id == ctx.tenant_id)
    pol_res = await db.execute(pol_q)
    pol = pol_res.scalars().first()
    if pol:
        policy_id = pol.id
    else:
        def_pol = Policy(
            tenant_id=ctx.tenant_id,
            policy_code=f"POL-BASE-{ctx.tenant_id}",
            title="Base Enterprise Compliance Policy",
            category="Governance",
            jurisdiction="GLOBAL",
        )
        db.add(def_pol)
        await db.flush()
        policy_id = def_pol.id

    control = Control(
        tenant_id=ctx.tenant_id,
        policy_id=policy_id,
        control_code=payload.control_code,
        name=payload.name,
        description=payload.description,
        control_type=payload.control_type,
        execution_type=payload.execution_type,
        frequency=payload.frequency,
        preventive_or_detective=payload.preventive_or_detective,
        business_unit_id=payload.business_unit_id,
        process_id=payload.process_id,
        system_id=payload.system_id,
        test_procedure=payload.test_procedure,
        evidence_requirements=payload.evidence_requirements,
        effectiveness_status="UNTESTED",
        status="ACTIVE",
    )
    db.add(control)
    await db.commit()
    await db.refresh(control)
    return ControlResponse(
        id=control.id,
        control_code=control.control_code,
        name=control.name,
        description=control.description,
        control_type=control.control_type,
        execution_type=control.execution_type,
        frequency=control.frequency,
        preventive_or_detective=control.preventive_or_detective,
        effectiveness_status=control.effectiveness_status,
        status=control.status,
        last_tested_at=control.last_tested_at,
        created_at=control.created_at,
    )
