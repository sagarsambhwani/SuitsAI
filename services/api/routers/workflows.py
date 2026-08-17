from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from database.postgres.models import WorkflowRun

router = APIRouter(prefix="/workflows", tags=["Workflow Orchestration & Runs"])


class WorkflowRunResponse(BaseModel):
    id: str
    tenant_id: str
    workflow_type: str
    status: str
    current_node: Optional[str]
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[WorkflowRunResponse])
async def list_workflow_runs(
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(WorkflowRun).where(WorkflowRun.tenant_id == ctx.tenant_id)
    result = await db.execute(query)
    runs = result.scalars().all()

    return [
        WorkflowRunResponse(
            id=r.id,
            tenant_id=r.tenant_id,
            workflow_type=r.workflow_type,
            status=r.status,
            current_node=r.current_node,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in runs
    ]
