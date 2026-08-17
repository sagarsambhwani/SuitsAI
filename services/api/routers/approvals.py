from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from database.postgres.models import PolicyChange, Policy, PolicyVersion, AuditEvent

router = APIRouter(prefix="/approvals", tags=["Human Review & Approval Gateway"])


class ApprovalActionRequest(BaseModel):
    action: str  # "APPROVE", "REJECT", "REVISE"
    comments: Optional[str] = "Approved by Compliance Officer after citation verification."


class ApprovalResponse(BaseModel):
    change_id: str
    status: str
    reviewed_by: str
    reviewed_at: datetime
    published_policy_version: Optional[str] = None
    audit_event_id: str


@router.post("/{change_id}/decision", response_model=ApprovalResponse)
async def submit_approval_decision(
    change_id: str,
    payload: ApprovalActionRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(PolicyChange).where(PolicyChange.id == change_id)
    result = await db.execute(query)
    change = result.scalar_one_or_none()

    if not change:
        raise HTTPException(status_code=404, detail="Policy change proposal not found")

    new_status = "APPROVED" if payload.action.upper() == "APPROVE" else "REJECTED"
    change.status = new_status
    change.reviewed_by = ctx.user_id
    change.reviewed_at = datetime.utcnow()

    published_version_num = None

    if new_status == "APPROVED":
        # Create published PolicyVersion in PostgreSQL
        pol_res = await db.execute(select(Policy).where(Policy.id == change.policy_id))
        policy = pol_res.scalar_one_or_none()

        if policy:
            curr_v = policy.current_version.split(".")
            new_v = f"{curr_v[0]}.{int(curr_v[1]) + 1}.0" if len(curr_v) >= 2 else "2.0.0"
            policy.current_version = new_v
            policy.updated_at = datetime.utcnow()
            published_version_num = new_v

            new_version = PolicyVersion(
                policy_id=policy.id,
                tenant_id=ctx.tenant_id,
                version_number=new_v,
                status="APPROVED",
                content_full=change.proposed_text,
                changelog=f"Amended per regulatory compliance change {change.id}: {change.justification}",
                approved_by=ctx.user_id,
                approved_at=datetime.utcnow(),
            )
            db.add(new_version)

    # Record immutable audit event
    audit = AuditEvent(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        event_type=f"POLICY_CHANGE_{new_status}",
        entity_type="PolicyChange",
        entity_id=change.id,
        action=new_status,
        details={
            "policy_id": change.policy_id,
            "change_type": change.change_type,
            "comments": payload.comments,
            "published_version": published_version_num,
        },
    )
    db.add(audit)
    await db.commit()

    return ApprovalResponse(
        change_id=change.id,
        status=new_status,
        reviewed_by=ctx.user_id,
        reviewed_at=change.reviewed_at,
        published_policy_version=published_version_num,
        audit_event_id=audit.id,
    )
