from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import RemediationAction, ComplianceGap
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/remediations", tags=["Remediation Actions"])


class RemediationCreate(BaseModel):
    gap_id: str
    action_type: str = "POLICY_REVISION"  # POLICY_REVISION, PROCEDURE_UPDATE, CONTROL_DEPLOYMENT, SYSTEM_CONFIG, TRAINING
    title: str
    description: str
    owner_id: Optional[str] = "Information Security Officer"
    accountable_id: Optional[str] = "Chief Compliance Officer"
    due_date: Optional[datetime] = None
    priority: str = "HIGH"


class RemediationStatusUpdate(BaseModel):
    status: str  # OPEN, ASSIGNED, IN_PROGRESS, BLOCKED, IMPLEMENTED, PENDING_TEST, FAILED_TEST, REOPENED, VALIDATED, CLOSED
    implementation_notes: Optional[str] = None


class RemediationResponse(BaseModel):
    id: str
    gap_id: str
    tenant_id: str
    action_type: str
    title: str
    description: str
    owner_id: Optional[str] = None
    priority: str
    status: str
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    validated_at: Optional[datetime] = None
    created_at: datetime


@router.get("", response_model=List[RemediationResponse])
async def list_remediations(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(RemediationAction).where(RemediationAction.tenant_id == ctx.tenant_id)
    if status:
        query = query.where(RemediationAction.status == status)
    result = await db.execute(query)
    remediations = result.scalars().all()
    return [
        RemediationResponse(
            id=r.id,
            gap_id=r.gap_id,
            tenant_id=r.tenant_id,
            action_type=r.action_type,
            title=r.title,
            description=r.description,
            owner_id=r.owner_id,
            priority=r.priority,
            status=r.status,
            due_date=r.due_date,
            completed_at=r.completed_at,
            validated_at=r.validated_at,
            created_at=r.created_at,
        )
        for r in remediations
    ]


@router.post("", response_model=RemediationResponse)
async def create_remediation(
    payload: RemediationCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    rem = RemediationAction(
        gap_id=payload.gap_id,
        tenant_id=ctx.tenant_id,
        action_type=payload.action_type,
        title=payload.title,
        description=payload.description,
        owner_id=payload.owner_id,
        accountable_id=payload.accountable_id,
        due_date=payload.due_date,
        priority=payload.priority,
        status="OPEN",
    )
    db.add(rem)
    await db.commit()
    await db.refresh(rem)
    return RemediationResponse(
        id=rem.id,
        gap_id=rem.gap_id,
        tenant_id=rem.tenant_id,
        action_type=rem.action_type,
        title=rem.title,
        description=rem.description,
        owner_id=rem.owner_id,
        priority=rem.priority,
        status=rem.status,
        due_date=rem.due_date,
        completed_at=rem.completed_at,
        validated_at=rem.validated_at,
        created_at=rem.created_at,
    )


@router.patch("/{id}/status", response_model=RemediationResponse)
async def update_remediation_status(
    id: str,
    payload: RemediationStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(RemediationAction).where(
        RemediationAction.id == id,
        RemediationAction.tenant_id == ctx.tenant_id,
    )
    result = await db.execute(query)
    rem = result.scalar_one_or_none()
    if not rem:
        raise HTTPException(status_code=404, detail="Remediation action not found")

    rem.status = payload.status
    if payload.implementation_notes:
        rem.implementation_notes = payload.implementation_notes

    if payload.status in ("IMPLEMENTED", "VALIDATED", "CLOSED"):
        rem.completed_at = datetime.utcnow()
    if payload.status == "VALIDATED":
        rem.validated_at = datetime.utcnow()

    # If closed, update gap status
    if payload.status == "CLOSED":
        gap_q = select(ComplianceGap).where(ComplianceGap.id == rem.gap_id)
        gap_res = await db.execute(gap_q)
        gap = gap_res.scalar_one_or_none()
        if gap:
            gap.status = "CLOSED"

    await db.commit()
    await db.refresh(rem)

    return RemediationResponse(
        id=rem.id,
        gap_id=rem.gap_id,
        tenant_id=rem.tenant_id,
        action_type=rem.action_type,
        title=rem.title,
        description=rem.description,
        owner_id=rem.owner_id,
        priority=rem.priority,
        status=rem.status,
        due_date=rem.due_date,
        completed_at=rem.completed_at,
        validated_at=rem.validated_at,
        created_at=rem.created_at,
    )
