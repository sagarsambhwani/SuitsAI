from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.postgres.connection import get_db_session
from database.postgres.models import InternalDocument
from services.api.dependencies import get_tenant_context, TenantContext, require_permissions

router = APIRouter(prefix="/internal-documents", tags=["Internal Governance Documents"])


class InternalDocumentCreate(BaseModel):
    document_type: str = "POLICY"  # POLICY, STANDARD, PROCEDURE, SOP, MANUAL, WORK_INSTRUCTION, GUIDELINE, TRAINING_MATERIAL, CONTRACT, CONTROL_DOCUMENT
    doc_code: str
    title: str
    owner_id: Optional[str] = "Compliance & Legal"
    business_unit_id: Optional[str] = "Operations"
    jurisdiction: str = "GLOBAL"
    version: str = "1.0.0"
    content_full: Optional[str] = None


class InternalDocumentResponse(BaseModel):
    id: str
    tenant_id: str
    document_type: str
    doc_code: str
    title: str
    owner_id: Optional[str] = None
    business_unit_id: Optional[str] = None
    jurisdiction: str
    version: str
    status: str
    effective_from: datetime
    created_at: datetime


@router.get("", response_model=List[InternalDocumentResponse])
async def list_internal_documents(
    doc_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(get_tenant_context),
):
    query = select(InternalDocument).where(InternalDocument.tenant_id == ctx.tenant_id)
    if doc_type:
        query = query.where(InternalDocument.document_type == doc_type)
    result = await db.execute(query)
    docs = result.scalars().all()
    return [
        InternalDocumentResponse(
            id=d.id,
            tenant_id=d.tenant_id,
            document_type=d.document_type,
            doc_code=d.doc_code,
            title=d.title,
            owner_id=d.owner_id,
            business_unit_id=d.business_unit_id,
            jurisdiction=d.jurisdiction,
            version=d.version,
            status=d.status,
            effective_from=d.effective_from,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.post("", response_model=InternalDocumentResponse)
async def create_internal_document(
    payload: InternalDocumentCreate,
    db: AsyncSession = Depends(get_db_session),
    ctx: TenantContext = Depends(require_permissions(["policy:write"])),
):
    doc = InternalDocument(
        tenant_id=ctx.tenant_id,
        document_type=payload.document_type,
        doc_code=payload.doc_code,
        title=payload.title,
        owner_id=payload.owner_id,
        business_unit_id=payload.business_unit_id,
        jurisdiction=payload.jurisdiction,
        version=payload.version,
        content_full=payload.content_full,
        status="ACTIVE",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return InternalDocumentResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        document_type=doc.document_type,
        doc_code=doc.doc_code,
        title=doc.title,
        owner_id=doc.owner_id,
        business_unit_id=doc.business_unit_id,
        jurisdiction=doc.jurisdiction,
        version=doc.version,
        status=doc.status,
        effective_from=doc.effective_from,
        created_at=doc.created_at,
    )
