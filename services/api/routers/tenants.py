from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional

from database.postgres.connection import get_db_session
from database.postgres.models import Tenant

router = APIRouter(prefix="/tenants", tags=["Tenants"])


class TenantCreate(BaseModel):
    name: str
    slug: str
    tier: str = "standard"


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    tier: str
    is_active: bool


@router.get("", response_model=List[TenantResponse])
async def list_tenants(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            tier=t.tier,
            is_active=t.is_active,
        )
        for t in tenants
    ]


@router.post("", response_model=TenantResponse)
async def create_tenant(payload: TenantCreate, db: AsyncSession = Depends(get_db_session)):
    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
        tier=payload.tier,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        tier=tenant.tier,
        is_active=tenant.is_active,
    )
