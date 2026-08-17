from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from services.ingestion.hasher import calculate_sha256
from services.ingestion.s3_storage import get_document_storage
from services.ingestion.parser import DocumentParser

router = APIRouter(prefix="/documents", tags=["Document Lake & Ingestion"])


class DocumentUploadResponse(BaseModel):
    document_id: str
    sha256_hash: str
    storage_uri: str
    file_type: str
    parsed_sections_count: int
    extracted_requirements_count: int
    chunks_count: int
    title: str


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_and_ingest_document(
    file: UploadFile = File(...),
    doc_type: str = Form("Circular"),
    jurisdiction: str = Form("GLOBAL"),
    regulator: str = Form("Central Bank"),
    code: str = Form("REG-2026"),
    use_ocr: bool = Form(False),
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    content_bytes = await file.read()
    filename = file.filename or "regulatory_doc.txt"
    
    # 1. Compute Immutable SHA-256 Hash
    sha256_hash = calculate_sha256(content_bytes)

    # 2. Store in S3 / Local Document Lake
    storage = get_document_storage()
    storage_uri = storage.store_document(
        folder="raw",
        entity_path=f"{regulator}/{code}",
        filename=filename,
        content=content_bytes,
    )

    # 3. Parse Sections, Requirements & Semantic/Structural Chunks
    parsed = DocumentParser.parse_file_bytes(
        file_bytes=content_bytes,
        filename=filename,
        default_code=code,
        default_regulator=regulator,
        default_jurisdiction=jurisdiction,
    )

    return DocumentUploadResponse(
        document_id=f"DOC-{sha256_hash[:12]}",
        sha256_hash=sha256_hash,
        storage_uri=storage_uri,
        file_type=filename.split(".")[-1].lower() if "." in filename else "txt",
        parsed_sections_count=len(parsed.sections),
        extracted_requirements_count=len(parsed.extracted_requirements),
        chunks_count=len(parsed.chunks),
        title=parsed.title,
    )
