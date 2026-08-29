from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ComplianceException, ComplianceGap
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/exceptions", tags=["Compliance Exceptions & Waivers"])


class ExceptionRequest(BaseModel):
    gap_id: str
    reason: str
    compensating_control: str
    residual_risk: str = "MEDIUM"
    expiry_date: datetime
    review_date: datetime


class ExceptionResponse(BaseModel):
    id: str
    gap_id: str
    tenant_id: str
    reason: str
    compensating_control: str
    residual_risk: str
    owner_id: str
    approver_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    expiry_date: datetime
    review_date: datetime
    status: str
    created_at: datetime


@router.get("", response_model=List[ExceptionResponse])
async def list_exceptions(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ComplianceException).where(ComplianceException.tenant_id == ctx.tenant_id)
    if status:
        query = query.where(ComplianceException.status == status)
    result = await db.execute(query)
    exceptions = result.scalars().all()
    return [
        ExceptionResponse(
            id=e.id,
            gap_id=e.gap_id,
            tenant_id=e.tenant_id,
            reason=e.reason,
            compensating_control=e.compensating_control,
            residual_risk=e.residual_risk,
            owner_id=e.owner_id,
            approver_id=e.approver_id,
            approved_at=e.approved_at,
            expiry_date=e.expiry_date,
            review_date=e.review_date,
            status=e.status,
            created_at=e.created_at,
        )
        for e in exceptions
    ]


@router.post("", response_model=ExceptionResponse)
async def request_exception(
    payload: ExceptionRequest,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    exc = ComplianceException(
        gap_id=payload.gap_id,
        tenant_id=ctx.tenant_id,
        reason=payload.reason,
        compensating_control=payload.compensating_control,
        residual_risk=payload.residual_risk,
        owner_id=ctx.user_id,
        expiry_date=payload.expiry_date,
        review_date=payload.review_date,
        status="REQUESTED",
    )
    db.add(exc)
    await db.commit()
    await db.refresh(exc)
    return ExceptionResponse(
        id=exc.id,
        gap_id=exc.gap_id,
        tenant_id=exc.tenant_id,
        reason=exc.reason,
        compensating_control=exc.compensating_control,
        residual_risk=exc.residual_risk,
        owner_id=exc.owner_id,
        approver_id=exc.approver_id,
        approved_at=exc.approved_at,
        expiry_date=exc.expiry_date,
        review_date=exc.review_date,
        status=exc.status,
        created_at=exc.created_at,
    )


@router.post("/{id}/approve", response_model=ExceptionResponse)
async def approve_exception(
    id: str,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(require_permissions(["policy:publish"])),
):
    query = select(ComplianceException).where(
        ComplianceException.id == id,
        ComplianceException.tenant_id == ctx.tenant_id,
    )
    result = await db.execute(query)
    exc = result.scalar_one_or_none()
    if not exc:
        raise HTTPException(status_code=404, detail="Exception request not found")

    exc.status = "APPROVED"
    exc.approver_id = ctx.user_id
    exc.approved_at = datetime.utcnow()

    # Update gap status to RISK_ACCEPTED
    gap_q = select(ComplianceGap).where(ComplianceGap.id == exc.gap_id)
    gap_res = await db.execute(gap_q)
    gap = gap_res.scalar_one_or_none()
    if gap:
        gap.status = "RISK_ACCEPTED"

    await db.commit()
    await db.refresh(exc)

    return ExceptionResponse(
        id=exc.id,
        gap_id=exc.gap_id,
        tenant_id=exc.tenant_id,
        reason=exc.reason,
        compensating_control=exc.compensating_control,
        residual_risk=exc.residual_risk,
        owner_id=exc.owner_id,
        approver_id=exc.approver_id,
        approved_at=exc.approved_at,
        expiry_date=exc.expiry_date,
        review_date=exc.review_date,
        status=exc.status,
        created_at=exc.created_at,
    )
