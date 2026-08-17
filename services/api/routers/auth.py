from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from services.api.dependencies import TenantContext, get_current_tenant_context

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str = "BANK-GLOBAL-001"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    tenant_id: str
    user_email: str
    role: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    # Standard authentication endpoint
    return TokenResponse(
        access_token="mock_jwt_token_for_compliance_officer",
        token_type="bearer",
        tenant_id=req.tenant_slug,
        user_email=req.email,
        role="compliance_officer",
    )


@router.get("/me")
async def get_current_user_profile(ctx: TenantContext = Depends(get_current_tenant_context)):
    return {
        "user_id": ctx.user_id,
        "tenant_id": ctx.tenant_id,
        "role": ctx.role,
        "permissions": [
            "policy:read",
            "policy:write",
            "compliance:analyze",
            "compliance:approve",
            "audit:read",
        ],
    }
