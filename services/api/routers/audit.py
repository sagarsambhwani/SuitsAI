from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from database.postgres.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["Immutable Audit Trail & Compliance Lineage"])


class AuditEventResponse(BaseModel):
    id: str
    tenant_id: str
    user_id: Optional[str]
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    details: Dict[str, Any] = {}
    timestamp: datetime


@router.get("", response_model=List[AuditEventResponse])
async def list_audit_events(
    event_type: Optional[str] = None,
    limit: int = 50,
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(AuditEvent).where(AuditEvent.tenant_id == ctx.tenant_id)
    if event_type:
        query = query.where(AuditEvent.event_type == event_type)
    query = query.order_by(desc(AuditEvent.timestamp)).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        AuditEventResponse(
            id=e.id,
            tenant_id=e.tenant_id,
            user_id=e.user_id,
            event_type=e.event_type,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            action=e.action,
            details=e.details or {},
            timestamp=e.timestamp,
        )
        for e in events
    ]
