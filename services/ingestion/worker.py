import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from services.ingestion.hasher import calculate_sha256
from services.ingestion.s3_storage import get_document_storage
from services.ingestion.parser import DocumentParser, ParsedDocument
from ai.models.embeddings import get_embedding_gateway
from ai.llamaindex.indexes import IndexedDocumentNode, get_index_registry
from services.graph.client import get_graph_client
from services.graph.ontology import GraphNode, GraphRelationship

logger = logging.getLogger(__name__)


class IngestionJobStatus:
    QUEUED = "QUEUED"
    EXTRACTING_LAYOUT = "EXTRACTING_LAYOUT"
    CHUNKING = "CHUNKING"
    EMBEDDING_BATCHES = "EMBEDDING_BATCHES"
    GRAPH_SYNC = "GRAPH_SYNC"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IngestionJob(BaseModel):
    job_id: str
    tenant_id: str
    filename: str
    code: str
    regulator: str
    jurisdiction: str
    status: str = IngestionJobStatus.QUEUED
    progress_percentage: int = 0
    total_sections: int = 0
    total_requirements: int = 0
    total_chunks: int = 0
    sha256_hash: Optional[str] = None
    storage_uri: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class IngestionJobManager:
    """
    Manages asynchronous, distributed ingestion jobs for large regulatory circulars,
    spreadsheets, and bank policy documents.
    """

    def __init__(self):
        self._jobs: Dict[str, IngestionJob] = {}

    def create_job(
        self,
        tenant_id: str,
        filename: str,
        code: str,
        regulator: str,
        jurisdiction: str,
    ) -> IngestionJob:
        job_id = f"JOB-{uuid.uuid4().hex[:12]}"
        job = IngestionJob(
            job_id=job_id,
            tenant_id=tenant_id,
            filename=filename,
            code=code,
            regulator=regulator,
            jurisdiction=jurisdiction,
        )
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        return self._jobs.get(job_id)

    def list_jobs(self, tenant_id: Optional[str] = None) -> List[IngestionJob]:
        if tenant_id:
            return [j for j in self._jobs.values() if j.tenant_id == tenant_id]
        return list(self._jobs.values())

    async def execute_ingestion_pipeline(
        self,
        job_id: str,
        file_bytes: bytes,
    ):
        """Asynchronous execution worker for non-blocking document ingestion."""
        job = self._jobs.get(job_id)
        if not job:
            return

        try:
            # 1. SHA-256 Checksum & S3 Storage
            job.status = IngestionJobStatus.EXTRACTING_LAYOUT
            job.progress_percentage = 15
            sha = calculate_sha256(file_bytes)
            job.sha256_hash = sha

            storage = get_document_storage()
            storage_uri = storage.store_document(
                folder="raw",
                entity_path=f"{job.regulator}/{job.code}",
                filename=job.filename,
                content=file_bytes,
            )
            job.storage_uri = storage_uri

            # 2. Layout-Aware Parsing & Extraction
            job.status = IngestionJobStatus.CHUNKING
            job.progress_percentage = 35
            parsed: ParsedDocument = DocumentParser.parse_file_bytes(
                file_bytes=file_bytes,
                filename=job.filename,
                default_code=job.code,
                default_regulator=job.regulator,
                default_jurisdiction=job.jurisdiction,
            )
            job.total_sections = len(parsed.sections)
            job.total_requirements = len(parsed.extracted_requirements)
            job.total_chunks = len(parsed.chunks)

            # 3. Batch Embedding Generation (Cohere Embed v4: 32-96 chunks per request)
            job.status = IngestionJobStatus.EMBEDDING_BATCHES
            job.progress_percentage = 65
            if parsed.chunks:
                embed_gw = get_embedding_gateway()
                chunk_texts = [c.text for c in parsed.chunks]
                vectors = await embed_gw.embed_documents(chunk_texts, input_type="search_document")

                # Index in DomainIndex
                index_registry = get_index_registry()
                reg_index = index_registry.get_index("RegulationIndex")
                nodes = []
                for chunk, vec in zip(parsed.chunks, vectors):
                    nodes.append(
                        IndexedDocumentNode(
                            id=chunk.chunk_id,
                            text=chunk.text,
                            doc_type="HIERARCHICAL_CHUNK",
                            metadata={
                                "tenant_id": job.tenant_id,
                                "document_code": chunk.document_code,
                                "section_number": chunk.section_number,
                                "heading": chunk.heading,
                                "jurisdiction": chunk.jurisdiction,
                                "regulator": chunk.regulator,
                                "risk_category": chunk.risk_category,
                                "obligation_type": chunk.obligation_type,
                            },
                            embedding=vec,
                        )
                    )
                for n in nodes:
                    reg_index.add_node(n)

            # 4. Knowledge Graph Synchronization
            job.status = IngestionJobStatus.GRAPH_SYNC
            job.progress_percentage = 85
            graph_client = get_graph_client()
            reg_node = GraphNode(
                id=job.code,
                label="Regulation",
                properties={
                    "code": job.code,
                    "title": parsed.title,
                    "regulator": job.regulator,
                    "jurisdiction": job.jurisdiction,
                    "sha256": sha,
                    "status": "ACTIVE",
                },
            )
            graph_client.sync_node(reg_node)

            for req in parsed.extracted_requirements:
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
                        "jurisdiction": job.jurisdiction,
                    },
                )
                graph_client.sync_node(req_node)
                graph_client.sync_relationship(
                    GraphRelationship(
                        source_id=reg_node.id,
                        target_id=req_node.id,
                        rel_type="CONTAINS",
                        source_evidence_id=sha,
                        extraction_run_id=job.job_id,
                        method="ASYNC_WORKER",
                        confidence=1.0,
                        reviewer_status="VERIFIED",
                    )
                )

            # 5. Completed
            job.status = IngestionJobStatus.COMPLETED
            job.progress_percentage = 100
            job.completed_at = datetime.utcnow()
            logger.info(f"[Ingestion Worker] Completed job {job_id} for {job.filename}")

        except Exception as e:
            logger.error(f"[Ingestion Worker] Job {job_id} failed: {e}", exc_info=True)
            job.status = IngestionJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()


_job_manager = None


def get_job_manager() -> IngestionJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = IngestionJobManager()
    return _job_manager
