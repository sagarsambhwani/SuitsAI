import pytest
import io
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

from services.ingestion.extractors import (
    FileExtractorRouter,
    PlainTextExtractor,
    DocxExtractor,
    ExcelExtractor,
    PptxExtractor,
    PDFExtractor,
)
from services.ingestion.parser import DocumentParser
from ai.models.embeddings import (
    MockEmbeddingGateway,
    BedrockCohereEmbeddingGateway,
    MockRerankerGateway,
    get_embedding_gateway,
    get_reranker_gateway,
)
from ai.llamaindex.indexes import DomainIndex, IndexedDocumentNode
from ai.llamaindex.retriever import PreFilteredHybridRetriever


def test_plain_text_and_router_extraction():
    content = b"""Section 4.1 Enhanced Due Diligence:
    All high-risk customers shall undergo periodic enhanced due diligence every 180 days, except when exempted by central authority.
    """
    payload = FileExtractorRouter.extract(content, filename="rbi_circular.txt")
    assert payload.file_type == "text"
    assert "Enhanced Due Diligence" in payload.full_text
    assert len(payload.pages) >= 1


def test_docx_extractor_with_mock_xml():
    # Build a lightweight in-memory docx zip
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p><w:r><w:t>Section 2.1 Customer Identification Program</w:t></w:r></w:p>
                <w:p><w:r><w:t>Regulated entities must verify official identity documents.</w:t></w:r></w:p>
            </w:body>
        </w:document>"""
        z.writestr("word/document.xml", doc_xml.encode("utf-8"))
    
    docx_bytes = bio.getvalue()
    payload = FileExtractorRouter.extract(docx_bytes, filename="policy_draft.docx")
    assert payload.file_type == "docx"
    assert "Customer Identification Program" in payload.full_text
    assert "official identity documents" in payload.full_text


def test_xlsx_csv_extractor():
    csv_bytes = b"Rule_ID,Category,Requirement\nREQ-01,AML,Video KYC is mandatory\nREQ-02,Security,Rotate keys every 90 days\n"
    payload = FileExtractorRouter.extract(csv_bytes, filename="rules_matrix.csv")
    assert payload.file_type == "csv"
    assert "REQ-01" in payload.full_text
    assert "Rotate keys every 90 days" in payload.full_text
    assert len(payload.tables) == 1


def test_pptx_extractor_with_mock_xml():
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as z:
        slide_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
            <p:cSld>
                <p:spTree>
                    <p:sp>
                        <p:txBody>
                            <a:p><a:r><a:t>Compliance Architecture 2026</a:t></a:r></a:p>
                            <a:p><a:r><a:t>Section 1: Zero Trust Authorization shall be enforced.</a:t></a:r></a:p>
                        </p:txBody>
                    </p:sp>
                </p:spTree>
            </p:cSld>
        </p:sld>"""
        z.writestr("ppt/slides/slide1.xml", slide_xml.encode("utf-8"))
    
    pptx_bytes = bio.getvalue()
    payload = FileExtractorRouter.extract(pptx_bytes, filename="overview.pptx")
    assert payload.file_type == "pptx"
    assert "Compliance Architecture 2026" in payload.full_text


def test_document_parser_hierarchical_chunking():
    text = """
    Section 4.1 Enhanced Due Diligence:
    Regulated entities shall perform enhanced due diligence for all foreign PEP customers.
    
    Section 4.2 Automated Transaction Monitoring:
    All cross-border transactions exceeding USD 10000 must trigger automated AML screening, except when pre-cleared by compliance officer.
    """
    parsed = DocumentParser.parse_regulatory_text(
        text=text,
        default_code="RBI/2026/01",
        default_regulator="RBI",
        default_jurisdiction="IN",
    )

    assert len(parsed.sections) == 2
    assert len(parsed.extracted_requirements) == 2
    assert len(parsed.chunks) >= 2
    
    chunk = parsed.chunks[0]
    assert chunk.document_code == "RBI/2026/01"
    assert chunk.jurisdiction == "IN"
    assert chunk.regulator == "RBI"
    assert "Section 4.1" in chunk.text


@pytest.mark.asyncio
async def test_embedding_and_reranking_gateways():
    embed_gw = MockEmbeddingGateway(dimension=128)
    texts = ["Requirement for KYC retention", "Enhanced due diligence for high-risk accounts"]
    
    # 1. Batch document embedding
    doc_vectors = await embed_gw.embed_documents(texts, input_type="search_document")
    assert len(doc_vectors) == 2
    assert len(doc_vectors[0]) == 128
    
    # 2. Single query embedding
    query_vec = await embed_gw.embed_query("KYC retention", input_type="search_query")
    assert len(query_vec) == 128

    # 3. Reranker gateway
    rerank_gw = MockRerankerGateway()
    docs = [
        {"id": "doc1", "text": "Unrelated topic regarding cloud storage pricing"},
        {"id": "doc2", "text": "Mandatory KYC document retention period is 10 years"},
    ]
    reranked = await rerank_gw.rerank(query="KYC retention period", documents=docs, top_n=2)
    assert len(reranked) == 2
    assert reranked[0]["id"] == "doc2"
    assert reranked[0]["relevance_score"] > reranked[1]["relevance_score"]


@pytest.mark.asyncio
async def test_hybrid_search_and_retriever_pipeline():
    index = DomainIndex("TestRegulationIndex")
    node1 = IndexedDocumentNode(
        id="NODE-01",
        text="Section 4.3 Enhanced Due Diligence for High-Risk Customers and NBFCs.",
        doc_type="REQUIREMENT",
        metadata={"tenant_id": "BANK-01", "jurisdiction": "IN", "regulator": "RBI"},
    )
    node2 = IndexedDocumentNode(
        id="NODE-02",
        text="Section 8.1 API Key rotation interval every 90 days.",
        doc_type="REQUIREMENT",
        metadata={"tenant_id": "BANK-01", "jurisdiction": "IN", "regulator": "RBI"},
    )
    node3 = IndexedDocumentNode(
        id="NODE-03",
        text="Section 1.0 Foreign branch policy under US jurisdiction.",
        doc_type="REQUIREMENT",
        metadata={"tenant_id": "BANK-02", "jurisdiction": "US", "regulator": "OCC"},
    )

    await index.add_nodes_batch([node1, node2, node3])

    # 1. Hybrid search with pre-retrieval tenant/jurisdiction filtering
    results = await index.search_hybrid(
        query="due diligence high-risk customer",
        filters={"jurisdiction": "IN"},
        top_k=2,
    )
    assert len(results) == 2
    assert results[0].id == "NODE-01"

    # 2. Pipeline retrieval with Cohere Rerank 3.5
    from ai.llamaindex.indexes import get_index_registry
    reg = get_index_registry()
    reg.regulation_index = index
    retriever = PreFilteredHybridRetriever(registry=reg)

    reranked_pipeline = await retriever.retrieve_with_rerank(
        query="high-risk due diligence requirements",
        index_name="RegulationIndex",
        filters={"jurisdiction": "IN"},
        top_k=1,
    )
    assert len(reranked_pipeline) == 1
    assert reranked_pipeline[0]["id"] == "NODE-01"
