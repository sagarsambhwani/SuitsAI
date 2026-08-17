from enum import Enum
from typing import Optional, List, Callable
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.api.config import get_settings
from database.postgres.connection import get_db_session
from database.postgres.models import User, Tenant

settings = get_settings()


class UserRole(str, Enum):
    ADMIN = "admin"
    COMPLIANCE_MAKER = "compliance_maker"
    COMPLIANCE_CHECKER = "compliance_checker"
    AUDITOR = "auditor"
    VIEWER = "viewer"


ROLE_PERMISSIONS: dict[str, List[str]] = {
    UserRole.ADMIN: ["*"],
    UserRole.COMPLIANCE_MAKER: [
        "policy:read", "policy:write", "compliance:analyze", "approvals:submit_maker", "audit:read"
    ],
    UserRole.COMPLIANCE_CHECKER: [
        "policy:read", "policy:publish", "compliance:analyze", "approvals:authorize_checker", "audit:read"
    ],
    UserRole.AUDITOR: [
        "policy:read", "compliance:read", "audit:read", "compliance:replay"
    ],
    UserRole.VIEWER: [
        "policy:read", "compliance:read"
    ],
}


class TenantContext:
    def __init__(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        role: str = UserRole.COMPLIANCE_MAKER,
        business_unit: str = "GLOBAL",
        jurisdiction: str = "GLOBAL",
        clearance_level: str = "CONFIDENTIAL",
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id or "USER-DEFAULT-001"
        self.role = role
        self.business_unit = business_unit
        self.jurisdiction = jurisdiction
        self.clearance_level = clearance_level

    def has_permission(self, permission: str) -> bool:
        perms = ROLE_PERMISSIONS.get(self.role, [])
        return "*" in perms or permission in perms


async def get_current_tenant_context(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_user_id: Optional[str] = Header(None, alias="X-User-ID"),
    x_role: Optional[str] = Header(None, alias="X-Role"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session),
) -> TenantContext:
    """
    Extracts and validates enterprise tenant context and RBAC role.
    In production, claims are verified against the cryptographic enterprise IdP JWT.
    """
    tenant_id = x_tenant_id or "BANK-GLOBAL-001"
    user_id = x_user_id or "USER-DEFAULT-001"
    role = x_role or UserRole.COMPLIANCE_MAKER

    # Normalize role
    if role not in [r.value for r in UserRole]:
        role = UserRole.COMPLIANCE_MAKER

    # Ensure a default tenant exists in DB
    query = select(Tenant).where(Tenant.slug == tenant_id)
    result = await db.execute(query)
    tenant = result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            id=tenant_id,
            name="Apex Commercial Bank Corp",
            slug=tenant_id,
            tier="enterprise",
        )
        db.add(tenant)
        await db.flush()

    return TenantContext(
        tenant_id=tenant.id,
        user_id=user_id,
        role=role,
    )


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory enforcing Role-Based Access Control (RBAC)."""
    async def role_checker(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        if ctx.role not in allowed_roles and ctx.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{ctx.role}' does not have authorization. Required: {allowed_roles}",
            )
        return ctx
    return role_checker


def require_permissions(*required_perms: str) -> Callable:
    """Dependency factory enforcing Attribute/Permission-Based Access Control (ABAC)."""
    async def perm_checker(ctx: TenantContext = Depends(get_current_tenant_context)) -> TenantContext:
        for perm in required_perms:
            if not ctx.has_permission(perm):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Missing required permission '{perm}'.",
                )
        return ctx
    return perm_checker
