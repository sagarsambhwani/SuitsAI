# SuitsAI Architecture Guide

> **Production Banking & Compliance Document RAG Platform on AWS**
> Enterprise Two-Plane Architecture: Ingestion/Indexing Plane + Online Query/Reasoning Plane

---

## 1. System Overview

SuitsAI is an enterprise compliance, policy management, and regulatory gap analysis platform purpose-built for regulated financial institutions (Commercial Banks, NBFCs, and Digital Lending Entities). 

Unlike generic RAG architectures that treat legal documents as unstructured text and leave accuracy entirely to generative LLMs, SuitsAI operates on five foundational tenets:

1. **RAG Retrieves Evidence**: Hybrid vector and exact keyword search over an immutable S3 document lake.
2. **Knowledge Graph Models Structure**: Neo4j GraphRAG maps regulatory mandates to internal bank policies, clauses, controls, and business units.
3. **Deterministic Rules Enforce Compliance**: An independent 8-Gate Verification Engine validates claims before any AI artifact is accepted.
4. **LLMs Interpret and Draft**: Multi-tier Bedrock model routing (Claude 3.5 Sonnet / Haiku) generates structured deltas and amendments.
5. **Auditors Control Production Changes**: Human review gateways and frozen point-in-time snapshots (`ComplianceRunSnapshot`) ensure 100% regulatory auditability.

---

## 2. Target Two-Plane Architecture

```text
                         ┌───────────────────────────────────────┐
                         │          BANKING DATA SOURCES         │
                         │                                       │
                         │  PDFs │ DOCX │ PPTX │ XLSX │ Scans   │
                         │  RBI  │ Contracts │ Policies │ Audit │
                         └───────────────────┬───────────────────┘
                                             │
                                             ▼
                            ┌──────────────────────────────┐
                            │      Amazon S3 Lake          │
                            │                              │
                            │ Raw documents + SHA-256      │
                            │ Document versions            │
                            │ Page / Slide images          │
                            └──────────────┬───────────────┘
                                           │
                             S3 Event / EventBridge / SQS
                                           │
                                           ▼
                    ┌───────────────────────────────────────────┐
                    │             INGESTION PLANE                │
                    │                                           │
                    │ FileExtractorRouter (PDF/Textract/Office) │
                    │ Structural + Semantic Chunker             │
                    │ Obligation, Exception & Risk Classifier   │
                    │ Neo4j Graph Topology Sync                 │
                    └────────────────────┬──────────────────────┘
                                         │
                                         ▼
                      ┌─────────────────────────────────────┐
                      │       NORMALIZED DOCUMENT STORE     │
                      │                                     │
                      │ PostgreSQL: DocumentVersion,        │
                      │ RegulatorySection, RequirementVersion│
                      │ Neo4j: Regulation ──CONTAINS──► Req │
                      └─────────────────┬───────────────────┘
                                        │
                                        ▼
                         ┌────────────────────────────┐
                         │   Cohere Embed v4 / v3     │
                         │                            │
                         │ input_type: search_document│
                         │ batch 32–96 chunks/request │
                         └──────────────┬─────────────┘
                                        │
                                        ▼
             ┌───────────────────────────────────────────────────┐
             │                SEARCH / VECTOR LAYER               │
             │                                                   │
             │ Hybrid Vector (pgvector / OpenSearch)             │
             │ Exact BM25 Keyword Search                         │
             │ Pre-retrieval Tenant & Jurisdiction Isolation     │
             └────────────────────────────────┬──────────────────┘
                                              │
══════════════════════════════════════════════╪══════════════════════════
                                              │
                              ONLINE QUERY PLANE
                                              │
                         ┌────────────────────▼─────────────────┐
                         │          User / Application         │
                         │                                     │
                         │ "Can we onboard this customer?"     │
                         └────────────────────┬────────────────┘
                                              │
                                              ▼
                           ┌──────────────────────────────┐
                           │ API Gateway / ALB             │
                           │ JWT TenantContext Auth        │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │ LangGraph StateGraph          │
                           │                              │
                           │ 1. Pre-Retrieval Filters      │
                           │ 2. Requirement Extraction     │
                           │ 3. Neo4j Graph Impact Path    │
                           │ 4. Cross-Policy Gap Analysis  │
                           │ 5. Proposed Redline Drafting  │
                           └──────────────┬───────────────┘
                                          │
                      ┌───────────────────┴────────────────────┐
                      │                                        │
                      ▼                                        ▼
          ┌──────────────────────┐                ┌──────────────────────┐
          │ Cohere Embed v4      │                │ Exact BM25 Search    │
          │ input_type:          │                │ Clause numbers,      │
          │ search_query (single)│                │ Regulation codes     │
          └──────────┬───────────┘                └──────────┬───────────┘
                     │                                       │
                     └──────────────────┬────────────────────┘
                                        ▼
                            ┌─────────────────────────┐
                            │ Hybrid Retrieval        │
                            │ Vector top 50           │
                            │ Keyword top 50          │
                            │ Metadata Pre-filtering  │
                            └────────────┬────────────┘
                                         │
                                         ▼
                            ┌─────────────────────────┐
                            │ Cohere Rerank 3.5       │
                            │                         │
                            │ 50–100 candidates       │
                            │ → top 8–15 evidence     │
                            └────────────┬────────────┘
                                         │
                                         ▼
                           ┌─────────────────────────────┐
                           │ Bedrock Reasoning LLM       │
                           │ (Claude 3.5 Sonnet / Router)│
                           │                             │
                           │ Answer strictly from facts  │
                           │ Cite doc, version, page, sec│
                           └──────────────┬──────────────┘
                                          │
                                          ▼
                           ┌─────────────────────────────┐
                           │ 8-Gate Verification Engine  │
                           │                             │
                           │ Gate 1: Cryptographic Hash  │
                           │ Gate 2: Temporal Validity   │
                           │ Gate 3: Jurisdiction Match  │
                           │ Gate 4: Entity Scope        │
                           │ Gate 5: 100% Coverage       │
                           │ Gate 6: Exception Preserved │
                           │ Gate 7: Verbatim Citations  │
                           │ Gate 8: Contradiction Check │
                           └──────────────┬──────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────┐
                    │ Structured Compliance Response Contract │
                    │                                         │
                    │ Decision (COMPLIANT / GAP_DETECTED)     │
                    │ VerificationScorecard (8 Gate results)  │
                    │ Sentence-Level ClaimLineage             │
                    │ Proposed Redlines & Justification       │
                    └──────────────────┬──────────────────────┘
                                       │
                                       ▼
                         ┌─────────────────────────────┐
                         │ Immutable Audit & Replay    │
                         │                             │
                         │ ComplianceRunSnapshot       │
                         │ CloudWatch / CloudTrail     │
                         │ 6-Month Time-Travel Replay  │
                         └─────────────────────────────┘
```

---

## 3. Core Architectural Modules

### 1. Ingestion Lake & File Processing ([services/ingestion/](file:///e:/Downloads/VoyagerAI/services/ingestion/))
* **`hasher.py`**: Computes SHA-256 checksums over raw binary streams.
* **`s3_storage.py`**: Stores raw documents in partitioned S3 buckets (`raw/{regulator}/{code}/`).
* **`extractors.py`**: Native layout-aware parsers for PDF, scanned docs (AWS Textract), Word (`.docx`), Excel/CSV (`.xlsx`), PowerPoint (`.pptx`), and plain text.
* **`parser.py`**: Structural and semantic chunker generating 400–700 token chunks with 10–15% sliding window overlap and obligation tagging (`MANDATORY`, `CONDITIONAL`, `PROHIBITED`).

### 2. Knowledge Graph Topology & Provenance ([services/graph/](file:///e:/Downloads/VoyagerAI/services/graph/))
* Synchronizes nodes in Neo4j: `Regulation`, `Requirement`, `Policy`, `Clause`, `Control`, `BusinessUnit`.
* Traverses impact paths: $\text{Regulation} \longrightarrow \text{Requirement} \overset{\text{AFFECTS}}{\longrightarrow} \text{Policy} \overset{\text{CONTAINS}}{\longrightarrow} \text{Clause} \overset{\text{GOVERNS}}{\longrightarrow} \text{Control}$.

### 3. Embedding & Reranking Layer ([ai/models/embeddings.py](file:///e:/Downloads/VoyagerAI/ai/models/embeddings.py))
* **Cohere Embed v4 / v3**: Batch document embedding (`search_document`, up to 96 chunks per request) and single query embedding (`search_query`).
* **Cohere Rerank 3.5**: Cross-encoder reranking compressing 50–100 candidates down to top 8–15 precision evidence chunks.

### 4. Hybrid Semantic Retrieval ([ai/llamaindex/](file:///e:/Downloads/VoyagerAI/ai/llamaindex/))
* **`DomainIndex`**: Hybrid cosine vector similarity ($0.7$) + BM25 keyword matching ($0.3$).
* **`PreFilteredHybridRetriever`**: Applies pre-retrieval tenant isolation (`X-Tenant-ID`) and jurisdiction matching *before* similarity scoring.

### 5. LangGraph Orchestration & Multi-Model Router ([ai/langgraph/](file:///e:/Downloads/VoyagerAI/ai/langgraph/))
* Executes state machine over `ComplianceState`.
* `ModelRouter` delegates small tasks (classification) to lightweight models and complex gap analysis / policy drafting to Bedrock Claude 3.5 Sonnet.

### 6. Independent 8-Gate Verification Engine ([services/compliance/verification.py](file:///e:/Downloads/VoyagerAI/services/compliance/verification.py))
* Deterministic validator producing a machine-readable `VerificationScorecard`.
* Verifies sentence-level quotes, coverage percentage, statutory exception preservation, and detects obligation inversions.

### 7. Auditor Replay & Defensibility ([database/postgres/models.py](file:///e:/Downloads/VoyagerAI/database/postgres/models.py))
* `ComplianceRunSnapshot` freezes the complete matrix of input state, model version, prompt version, retrieved chunks, graph query snapshot, and verification scorecard to allow reproducing the exact run 6 months later.
