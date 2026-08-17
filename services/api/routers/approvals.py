import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from services.api.dependencies import (
    TenantContext,
    UserRole,
    get_current_tenant_context,
    require_roles,
)
from database.postgres.connection import get_db_session
from database.postgres.models import PolicyChange, Policy, PolicyVersion, AuditEvent

router = APIRouter(prefix="/approvals", tags=["Human Review & Dual-Control Maker-Checker Gateway"])


class MakerSubmitRequest(BaseModel):
    rationale: str = Field(..., description="Justification and compliance basis for proposed amendment")


class CheckerDecisionRequest(BaseModel):
    decision: str = Field(..., description="'APPROVE', 'REJECT', or 'REVISE'")
    checker_comments: str = Field(..., description="Formal signoff or rejection rationale")


class ApprovalActionRequest(BaseModel):
    action: str  # "APPROVE", "REJECT", "REVISE"
    comments: Optional[str] = "Approved by Compliance Officer after citation verification."


class MakerCheckerResponse(BaseModel):
    change_id: str
    maker_checker_status: str
    maker_id: Optional[str]
    maker_submitted_at: Optional[datetime]
    checker_id: Optional[str]
    checker_reviewed_at: Optional[datetime]
    digital_signature_hash: Optional[str]
    published_policy_version: Optional[str] = None
    audit_event_id: str


class ApprovalResponse(BaseModel):
    change_id: str
    status: str
    reviewed_by: str
    reviewed_at: datetime
    published_policy_version: Optional[str] = None
    audit_event_id: str


@router.post("/{change_id}/maker-submit", response_model=MakerCheckerResponse)
async def submit_by_maker(
    change_id: str,
    payload: MakerSubmitRequest,
    ctx: TenantContext = Depends(require_roles(UserRole.COMPLIANCE_MAKER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Step 1 of 4-Eyes Principle: Compliance Maker submits verified proposed amendment for senior review.
    """
    query = select(PolicyChange).where(PolicyChange.id == change_id)
    result = await db.execute(query)
    change = result.scalar_one_or_none()

    if not change:
        raise HTTPException(status_code=404, detail="Policy change proposal not found")

    change.maker_id = ctx.user_id
    change.maker_submitted_at = datetime.utcnow()
    change.maker_rationale = payload.rationale
    change.maker_checker_status = "MAKER_SUBMITTED"
    change.status = "PENDING_REVIEW"

    # Audit Trail
    audit = AuditEvent(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        event_type="MAKER_CHANGE_SUBMITTED",
        entity_type="PolicyChange",
        entity_id=change.id,
        action="MAKER_SUBMIT",
        details={
            "maker_id": ctx.user_id,
            "rationale": payload.rationale,
            "policy_id": change.policy_id,
        },
    )
    db.add(audit)
    await db.commit()

    return MakerCheckerResponse(
        change_id=change.id,
        maker_checker_status=change.maker_checker_status,
        maker_id=change.maker_id,
        maker_submitted_at=change.maker_submitted_at,
        checker_id=change.checker_id,
        checker_reviewed_at=change.checker_reviewed_at,
        digital_signature_hash=change.digital_signature_hash,
        audit_event_id=audit.id,
    )


@router.post("/{change_id}/checker-decision", response_model=MakerCheckerResponse)
async def authorize_by_checker(
    change_id: str,
    payload: CheckerDecisionRequest,
    ctx: TenantContext = Depends(require_roles(UserRole.COMPLIANCE_CHECKER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Step 2 of 4-Eyes Principle: Senior Compliance Checker / Officer authorizes or rejects change.
    Strictly enforces Maker != Checker separation of duties.
    """
    query = select(PolicyChange).where(PolicyChange.id == change_id)
    result = await db.execute(query)
    change = result.scalar_one_or_none()

    if not change:
        raise HTTPException(status_code=404, detail="Policy change proposal not found")

    # Enforce 4-Eyes Principle (Maker cannot check own proposal unless explicitly admin override)
    if change.maker_id and change.maker_id == ctx.user_id and ctx.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="4-Eyes Principle Violation: Checker cannot be the same user as the Maker.",
        )

    decision_upper = payload.decision.upper()
    new_status = "CHECKER_APPROVED" if decision_upper == "APPROVE" else "REJECTED"
    
    change.checker_id = ctx.user_id
    change.checker_reviewed_at = datetime.utcnow()
    change.checker_comments = payload.checker_comments
    change.maker_checker_status = new_status
    change.status = "APPROVED" if new_status == "CHECKER_APPROVED" else "REJECTED"
    change.reviewed_by = ctx.user_id
    change.reviewed_at = change.checker_reviewed_at

    published_version_num = None
    sig_hash = None

    if new_status == "CHECKER_APPROVED":
        # Generate tamper-evident digital signature hash of the approved amendment
        sig_payload = f"{change.id}:{change.proposed_text}:{change.maker_id}:{ctx.user_id}:{datetime.utcnow().isoformat()}"
        sig_hash = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()
        change.digital_signature_hash = sig_hash

        # Publish new PolicyVersion
        pol_res = await db.execute(select(Policy).where(Policy.id == change.policy_id))
        policy = pol_res.scalar_one_or_none()
        if not policy:
            # Create/link default policy for tenant
            policy = Policy(
                id=change.policy_id or f"POL-{ctx.tenant_id}",
                tenant_id=ctx.tenant_id,
                policy_code=f"POL-CORE-{ctx.tenant_id[:8]}",
                title="Enterprise Information Security & Compliance Policy",
                category="Security & Access Control",
                jurisdiction="IN",
                status="ACTIVE",
                current_version="1.0.0",
            )
            db.add(policy)
            await db.flush()

        curr_v = (policy.current_version or "1.0.0").split(".")
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
            changelog=f"4-Eyes Approved [Maker: {change.maker_id} | Checker: {ctx.user_id}]: {payload.checker_comments}",
            approved_by=ctx.user_id,
            approved_at=datetime.utcnow(),
        )
        db.add(new_version)

    # Immutable Audit Event
    audit = AuditEvent(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        event_type=f"CHECKER_DECISION_{new_status}",
        entity_type="PolicyChange",
        entity_id=change.id,
        action=new_status,
        details={
            "maker_id": change.maker_id,
            "checker_id": ctx.user_id,
            "comments": payload.checker_comments,
            "digital_signature_hash": sig_hash,
            "published_version": published_version_num,
        },
    )
    db.add(audit)
    await db.commit()

    return MakerCheckerResponse(
        change_id=change.id,
        maker_checker_status=change.maker_checker_status,
        maker_id=change.maker_id,
        maker_submitted_at=change.maker_submitted_at,
        checker_id=change.checker_id,
        checker_reviewed_at=change.checker_reviewed_at,
        digital_signature_hash=change.digital_signature_hash,
        published_policy_version=published_version_num,
        audit_event_id=audit.id,
    )


@router.post("/{change_id}/decision", response_model=ApprovalResponse)
async def submit_approval_decision(
    change_id: str,
    payload: ApprovalActionRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    """Standard approval decision (backward compatibility)."""
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
