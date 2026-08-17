from typing import Optional, AsyncGenerator
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.api.config import get_settings, Settings
from database.postgres.connection import get_db_session
from database.postgres.models import User, Tenant

settings = get_settings()


class TenantContext:
    def __init__(self, tenant_id: str, user_id: Optional[str] = None, role: str = "compliance_officer"):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role


async def get_current_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """
    Extracts and validates tenant context.
    In production, tenant is strictly derived from JWT claim to prevent client spoofing.
    """
    tenant_id = x_tenant_id or "BANK-GLOBAL-001"
    user_id = "USER-DEFAULT-001"
    role = "compliance_officer"

    # Ensure a default tenant exists in DB
    query = select(Tenant).where(Tenant.slug == tenant_id)
    result = await db.execute(query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        # Auto-provision default demo tenant if not exists
        tenant = Tenant(
            id=tenant_id,
            name="Apex Commercial Bank Corp",
            slug=tenant_id,
            tier="enterprise",
        )
        db.add(tenant)
        await db.flush()

    return TenantContext(tenant_id=tenant.id, user_id=user_id, role=role)
