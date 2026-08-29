from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ComplianceGap
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/gaps", tags=["Compliance Gaps"])


class GapCreate(BaseModel):
    obligation_id: str
    control_id: Optional[str] = None
    document_id: Optional[str] = None
    gap_type: str = "MISSING_CONTROL"
    description: str
    severity: str = "HIGH"


class GapResponse(BaseModel):
    id: str
    obligation_id: str
    tenant_id: str
    control_id: Optional[str] = None
    document_id: Optional[str] = None
    gap_type: str
    description: str
    severity: str
    status: str
    discovered_by: str
    created_at: datetime


@router.get("", response_model=List[GapResponse])
async def list_gaps(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ComplianceGap).where(ComplianceGap.tenant_id == ctx.tenant_id)
    if status:
        query = query.where(ComplianceGap.status == status)
    result = await db.execute(query)
    gaps = result.scalars().all()
    return [
        GapResponse(
            id=g.id,
            obligation_id=g.obligation_id,
            tenant_id=g.tenant_id,
            control_id=g.control_id,
            document_id=g.document_id,
            gap_type=g.gap_type,
            description=g.description,
            severity=g.severity,
            status=g.status,
            discovered_by=g.discovered_by,
            created_at=g.created_at,
        )
        for g in gaps
    ]


@router.post("", response_model=GapResponse)
async def create_gap(
    payload: GapCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    gap = ComplianceGap(
        obligation_id=payload.obligation_id,
        tenant_id=ctx.tenant_id,
        control_id=payload.control_id,
        document_id=payload.document_id,
        gap_type=payload.gap_type,
        description=payload.description,
        severity=payload.severity,
        discovered_by=ctx.user_id,
        status="OPEN",
    )
    db.add(gap)
    await db.commit()
    await db.refresh(gap)
    return GapResponse(
        id=gap.id,
        obligation_id=gap.obligation_id,
        tenant_id=gap.tenant_id,
        control_id=gap.control_id,
        document_id=gap.document_id,
        gap_type=gap.gap_type,
        description=gap.description,
        severity=gap.severity,
        status=gap.status,
        discovered_by=gap.discovered_by,
        created_at=gap.created_at,
    )
