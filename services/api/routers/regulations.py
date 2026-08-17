from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

from services.api.dependencies import TenantContext, get_current_tenant_context
from database.postgres.connection import get_db_session
from database.postgres.models import (
    Regulation,
    DocumentVersion,
    RegulatorySection,
    RequirementVersion,
    RegulatorySource,
)
from services.ingestion.parser import DocumentParser
from services.ingestion.hasher import calculate_sha256
from services.ingestion.s3_storage import get_document_storage
from services.graph.client import get_graph_client
from services.graph.ontology import GraphNode, GraphRelationship

router = APIRouter(prefix="/regulations", tags=["Regulations & Obligations (Layer 1 & Layer 2)"])


class RegulationIngestRequest(BaseModel):
    code: str  # e.g., "RBI/2026-27/04"
    title: str
    regulator_name: str  # e.g. "Reserve Bank of India"
    regulator_acronym: str = "RBI"
    jurisdiction: str = "IN"  # IN, US, UK, SG, EU
    doc_type: str = "Circular"  # Circular, Master Direction, Law
    publication_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    raw_text: str


class RequirementResponse(BaseModel):
    id: str
    req_code: str
    obligation_text: str
    obligation_type: str
    conditions: List[str] = []
    exceptions: List[str] = []
    risk_category: str
    applies_to: List[str] = []
    page_number: int = 1


class RegulationResponse(BaseModel):
    id: str
    code: str
    title: str
    doc_type: str
    jurisdiction: str
    current_version: str
    publication_date: datetime
    effective_date: datetime
    status: str
    sha256_hash: str
    requirements_count: int


@router.get("", response_model=List[RegulationResponse])
async def list_regulations(
    jurisdiction: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    query = select(Regulation)
    if jurisdiction:
        query = query.where(Regulation.jurisdiction == jurisdiction)
    result = await db.execute(query)
    regs = result.scalars().all()

    response = []
    for r in regs:
        # Fetch latest version
        ver_res = await db.execute(
            select(DocumentVersion).where(DocumentVersion.regulation_id == r.id).order_by(DocumentVersion.created_at.desc())
        )
        latest_ver = ver_res.scalars().first()

        req_count = 0
        sha = "N/A"
        pub_date = datetime.utcnow()
        eff_date = datetime.utcnow()

        if latest_ver:
            req_res = await db.execute(
                select(RequirementVersion).where(RequirementVersion.document_version_id == latest_ver.id)
            )
            req_count = len(req_res.scalars().all())
            sha = latest_ver.sha256_hash
            pub_date = latest_ver.publication_date
            eff_date = latest_ver.effective_date

        response.append(
            RegulationResponse(
                id=r.id,
                code=r.code,
                title=r.title,
                doc_type=r.doc_type,
                jurisdiction=r.jurisdiction,
                current_version=r.current_version,
                publication_date=pub_date,
                effective_date=eff_date,
                status=r.status,
                sha256_hash=sha,
                requirements_count=req_count,
            )
        )
    return response


@router.post("/ingest", response_model=RegulationResponse)
async def ingest_regulation(
    payload: RegulationIngestRequest,
    ctx: TenantContext = Depends(get_current_tenant_context),
    db: AsyncSession = Depends(get_db_session),
):
    # 1. Source check/create
    src_query = select(RegulatorySource).where(RegulatorySource.acronym == payload.regulator_acronym)
    src_res = await db.execute(src_query)
    source = src_res.scalar_one_or_none()

    if not source:
        source = RegulatorySource(
            name=payload.regulator_name,
            acronym=payload.regulator_acronym,
            jurisdiction=payload.jurisdiction,
        )
        db.add(source)
        await db.flush()

    # 2. Immutable SHA-256 Fingerprint & S3 Lake Store
    sha_hash = calculate_sha256(payload.raw_text)
    storage = get_document_storage()
    storage_uri = storage.store_document(
        folder="raw",
        entity_path=f"{payload.regulator_acronym}/{payload.code}",
        filename="circular_v1.txt",
        content=payload.raw_text,
    )

    # 3. Create Regulation & DocumentVersion
    pub_date = payload.publication_date or datetime.utcnow()
    eff_date = payload.effective_date or datetime.utcnow()

    reg_query = select(Regulation).where(Regulation.code == payload.code)
    reg_res = await db.execute(reg_query)
    regulation = reg_res.scalar_one_or_none()

    if not regulation:
        regulation = Regulation(
            source_id=source.id,
            code=payload.code,
            title=payload.title,
            doc_type=payload.doc_type,
            jurisdiction=payload.jurisdiction,
            current_version="1.0.0",
            status="ACTIVE",
        )
        db.add(regulation)
        await db.flush()

    # Calculate version number
    ver_res = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.regulation_id == regulation.id)
        .order_by(DocumentVersion.created_at.desc())
    )
    existing_versions = ver_res.scalars().all()
    next_ver = f"1.{len(existing_versions)}.0" if existing_versions else "1.0.0"
    regulation.current_version = next_ver

    doc_version = DocumentVersion(
        regulation_id=regulation.id,
        version_number=next_ver,
        sha256_hash=sha_hash,
        storage_uri=storage_uri,
        publication_date=pub_date,
        effective_date=eff_date,
        raw_content=payload.raw_text,
        metadata_payload={"word_count": len(payload.raw_text.split())},
    )
    db.add(doc_version)
    await db.flush()

    # 4. Parse Sections and Structured Requirements
    parsed = DocumentParser.parse_regulatory_text(
        text=payload.raw_text,
        default_code=payload.code,
        default_regulator=payload.regulator_name,
        default_jurisdiction=payload.jurisdiction,
    )

    graph_client = get_graph_client()

    # Sync to Neo4j with provenance
    reg_node = GraphNode(
        id=regulation.id,
        label="Regulation",
        properties={
            "code": regulation.code,
            "title": regulation.title,
            "doc_type": regulation.doc_type,
            "jurisdiction": regulation.jurisdiction,
            "sha256": sha_hash,
            "status": "ACTIVE",
        },
    )
    graph_client.sync_node(reg_node)

    for sec in parsed.sections:
        sec_obj = RegulatorySection(
            document_version_id=doc_version.id,
            section_number=sec.section_number,
            heading=sec.heading,
            page_number=sec.page_number,
            paragraph_index=sec.paragraph_index,
            content=sec.content,
            order_index=sec.order_index,
        )
        db.add(sec_obj)

    for req in parsed.extracted_requirements:
        req_obj = RequirementVersion(
            document_version_id=doc_version.id,
            req_code=req.req_code,
            obligation_text=req.obligation_text,
            obligation_type=req.obligation_type,
            conditions=req.conditions,
            exceptions=req.exceptions,
            applies_to=req.applies_to,
            risk_category=req.risk_category,
            extracted_by_model="claude-3-5-sonnet",
            extraction_prompt_version="v2.1",
        )
        db.add(req_obj)

        req_node = GraphNode(
            id=req.req_code,
            label="Requirement",
            properties={
                "req_code": req.req_code,
                "obligation_text": req.obligation_text,
                "obligation_type": req.obligation_type,
                "conditions": req.conditions,
                "exceptions": req.exceptions,
                "risk_category": req.risk_category,
                "jurisdiction": payload.jurisdiction,
            },
        )
        graph_client.sync_node(req_node)
        graph_client.sync_relationship(
            GraphRelationship(
                source_id=regulation.id,
                target_id=req_node.id,
                rel_type="CONTAINS",
                source_evidence_id=doc_version.id,
                extraction_run_id=f"INGEST-{sha_hash[:8]}",
                method="LLM_PARSER",
                confidence=1.0,
                reviewer_status="VERIFIED",
            )
        )

    await db.commit()

    return RegulationResponse(
        id=regulation.id,
        code=regulation.code,
        title=regulation.title,
        doc_type=regulation.doc_type,
        jurisdiction=regulation.jurisdiction,
        current_version=regulation.current_version,
        publication_date=pub_date,
        effective_date=eff_date,
        status=regulation.status,
        sha256_hash=sha_hash,
        requirements_count=len(parsed.extracted_requirements),
    )


@router.get("/{regulation_id}/requirements", response_model=List[RequirementResponse])
async def get_regulation_requirements(
    regulation_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    # Find latest document version for regulation
    ver_query = (
        select(DocumentVersion)
        .where(DocumentVersion.regulation_id == regulation_id)
        .order_by(DocumentVersion.created_at.desc())
    )
    ver_res = await db.execute(ver_query)
    doc_ver = ver_res.scalars().first()

    if not doc_ver:
        return []

    req_query = select(RequirementVersion).where(RequirementVersion.document_version_id == doc_ver.id)
    req_res = await db.execute(req_query)
    reqs = req_res.scalars().all()

    return [
        RequirementResponse(
            id=r.id,
            req_code=r.req_code,
            obligation_text=r.obligation_text,
            obligation_type=r.obligation_type,
            conditions=r.conditions or [],
            exceptions=r.exceptions or [],
            risk_category=r.risk_category,
            applies_to=r.applies_to or [],
            page_number=1,
        )
        for r in reqs
    ]
