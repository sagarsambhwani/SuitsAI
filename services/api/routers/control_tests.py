from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import ControlTest, Control, RemediationAction
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/control-tests", tags=["Control Testing"])


class ControlTestCreate(BaseModel):
    control_id: str
    test_type: str = "OPERATIONAL_EFFECTIVENESS"
    test_procedure: str
    testing_period: str = "Q1-2026"
    result: str = "PASS"  # PASS, PARTIAL, FAIL, NOT_TESTED
    findings: Optional[str] = None
    remediation_id_to_reopen: Optional[str] = None  # If test fails, reopen this remediation


class ControlTestResponse(BaseModel):
    id: str
    control_id: str
    tenant_id: str
    test_type: str
    testing_period: str
    result: str
    findings: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


@router.get("", response_model=List[ControlTestResponse])
async def list_control_tests(
    result_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(ControlTest).where(ControlTest.tenant_id == ctx.tenant_id)
    if result_filter:
        query = query.where(ControlTest.result == result_filter)
    res = await db.execute(query)
    tests = res.scalars().all()
    return [
        ControlTestResponse(
            id=t.id,
            control_id=t.control_id,
            tenant_id=t.tenant_id,
            test_type=t.test_type,
            testing_period=t.testing_period,
            result=t.result,
            findings=t.findings,
            started_at=t.started_at,
            completed_at=t.completed_at,
            created_at=t.created_at,
        )
        for t in tests
    ]


@router.post("", response_model=ControlTestResponse)
async def execute_control_test(
    payload: ControlTestCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    test = ControlTest(
        control_id=payload.control_id,
        tenant_id=ctx.tenant_id,
        test_type=payload.test_type,
        test_procedure=payload.test_procedure,
        testing_period=payload.testing_period,
        tester_id=ctx.user_id,
        result=payload.result,
        findings=payload.findings,
        completed_at=datetime.utcnow(),
    )
    db.add(test)

    # Update control effectiveness
    ctrl_q = select(Control).where(Control.id == payload.control_id)
    ctrl_res = await db.execute(ctrl_q)
    ctrl = ctrl_res.scalar_one_or_none()
    if ctrl:
        ctrl.last_tested_at = datetime.utcnow()
        ctrl.effectiveness_status = "EFFECTIVE" if payload.result == "PASS" else "DEFICIENT"

    # Reopen remediation if test fails
    if payload.result == "FAIL" and payload.remediation_id_to_reopen:
        rem_q = select(RemediationAction).where(RemediationAction.id == payload.remediation_id_to_reopen)
        rem_res = await db.execute(rem_q)
        rem = rem_res.scalar_one_or_none()
        if rem:
            rem.status = "REOPENED"
            rem.implementation_notes = f"Reopened due to Control Test {payload.result} failure: {payload.findings}"

    await db.commit()
    await db.refresh(test)

    return ControlTestResponse(
        id=test.id,
        control_id=test.control_id,
        tenant_id=test.tenant_id,
        test_type=test.test_type,
        testing_period=test.testing_period,
        result=test.result,
        findings=test.findings,
        started_at=test.started_at,
        completed_at=test.completed_at,
        created_at=test.created_at,
    )
