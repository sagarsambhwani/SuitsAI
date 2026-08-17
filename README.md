# SuitsAI — Enterprise AI Compliance & Bank Policy Platform

> **LangGraph + LlamaIndex + Neo4j + PostgreSQL (pgvector) + FastAPI on AWS**

---

## 1. Core Architectural Principle

```text
RAG retrieves evidence (LlamaIndex + S3 Document Lake + pgvector).
Knowledge Graph models relationships (Neo4j).
Rules determine compliance logic (Deterministic Rule Engine).
LLMs interpret and generate (Bedrock Claude 3.5 Sonnet / Multi-Model Router).
Human approval controls production changes (Approval Gateway & Immutable Audit).
```

---

## 2. System Architecture

```text
                         EXTERNAL SOURCES
 ┌───────────────────────────────────────────────────────────────┐
 │ Central Banks │ Regulators │ Government │ Bank Documents     │
 │ Circulars     │ Laws       │ Guidance   │ Policies / SOPs    │
 └───────────────────────────────┬───────────────────────────────┘
                                 │
                                 ▼
                       ┌──────────────────┐
                       │  Ingestion Lake  │
                       │   S3 + SHA-256   │
                       └────────┬─────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
             ┌─────────────┐        ┌─────────────┐
             │ LlamaIndex  │        │ Neo4j Graph │
             │ Parser/OCR  │        │ Ontology    │
             └──────┬──────┘        └──────┬──────┘
                    │                       │
                    └───────────┬───────────┘
                                ▼
                    ┌────────────────────────┐
                    │ LangGraph StateGraph   │
                    │ Impact & Gap Reasoning │
                    └────────────┬───────────┘
                                 │
             ┌───────────────────┼────────────────────┐
             ▼                   ▼                    ▼
       Requirement          Impact Analysis       Policy Draft
       Extraction           & Gap Detection       Generation
             │                   │                    │
             └───────────────────┼────────────────────┘
                                 ▼
                       ┌───────────────────┐
                       │ Independent       │
                       │ Verification &    │
                       │ Citation Check    │
                       └─────────┬─────────┘
                                 ▼
                       ┌───────────────────┐
                       │ Human Review      │
                       │ Gateway           │
                       └─────────┬─────────┘
                                 ▼
                       ┌───────────────────┐
                       │ Published Policy  │
                       │ + Immutable Audit │
                       └───────────────────┘
```

---

## 3. Directory Structure

```text
SuitsAI/
├── services/
│   ├── api/                     # Modular FastAPI routers (auth, tenants, documents, regulations, policies, compliance, workflows, approvals, audit)
│   ├── ingestion/               # Document parser, SHA-256 hasher, S3 lake storage
│   ├── graph/                   # Neo4j client, ontology, Cypher impact traversals
│   └── compliance/              # Independent citation validator & deterministic rules engine
├── ai/
│   ├── models/                  # Bedrock / OpenAI / Mock multi-model router
│   ├── llamaindex/              # Pre-filtered hybrid semantic retrievers & indexes
│   ├── langgraph/               # Compiled StateGraph reasoning pipeline (ComplianceState)
│   └── prompts/                 # Extraction, gap analysis, and policy drafting prompts
├── database/
│   ├── postgres/                # SQLAlchemy 2.0 async ORM models & session
│   └── neo4j/                   # Cypher schema, constraints, and indexes
├── frontend/                    # Modern, interactive Compliance Console (HTML5/CSS/JS)
├── infrastructure/
│   └── terraform/               # AWS Terraform IaC (ECS Fargate, RDS pgvector, S3 Lake, SQS, KMS)
├── tests/                       # Complete Pytest automated verification suite
├── Dockerfile                   # Production container
├── docker-compose.yml           # Local multi-service development stack
└── requirements.txt             # Python dependencies
```

---

## 4. Getting Started

### Local Setup (with Virtual Environment)

```powershell
# 1. Activate Virtual Environment
.\.venv\Scripts\Activate.ps1

# 2. Run Test Suite
pytest -v

# 3. Start Application Server
uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Accessing the Platform

- **Interactive Compliance Console**: `http://localhost:8000`
- **Interactive OpenAPI Documentation**: `http://localhost:8000/docs`
- **Health Check**: `http://localhost:8000/health`

---

## 5. Running with Docker Compose

To run the complete containerized stack (PostgreSQL + pgvector, Neo4j, Redis, LocalStack, and FastAPI):

```bash
docker-compose up --build
```

---

## 6. AWS Deployment (Terraform)

```bash
cd infrastructure/terraform
terraform init
terraform plan -var-file="environments/prod.tfvars"
terraform apply -var-file="environments/prod.tfvars"
```

---

## 7. Documentation & Architecture Decision Records (ADRs)

### Core Guides
* [System Architecture Guide](docs/architecture.md): Two-plane architecture, LangGraph reasoning, and 8-Gate verification.
* [Ingestion Pipeline & Document Processing](docs/ingestion_pipeline.md): Layout-aware multi-format parsing (PDF, Scans, Word, Excel, PPTX) and hierarchical semantic chunking.
* [Embeddings & Hybrid Retrieval](docs/embeddings_and_retrieval.md): Cohere Embed v4 batching, Cohere Rerank 3.5, and hybrid vector/BM25 retrieval.
* [API Reference & DTOs](docs/api_reference.md): Interactive REST endpoint contracts, schemas, and authentication headers.

### Architectural Decision Records (ADRs)
* [ADR-001: Two-Plane Architecture for Banking Compliance Document RAG](docs/adr/ADR-001_two_plane_architecture.md)
* [ADR-002: Layout-Aware Multi-Format Parsing vs. Flat Text Ingestion](docs/adr/ADR-002_layout_aware_multi_format_ingestion.md)
* [ADR-003: Hierarchical Semantic-Structural Chunking with Obligation Metadata](docs/adr/ADR-003_hierarchical_semantic_chunking.md)
* [ADR-004: Cohere Embed v4 Batching & Cohere Rerank 3.5 Two-Stage Retrieval](docs/adr/ADR-004_cohere_embed_v4_and_rerank_3_5_retrieval.md)
* [ADR-005: Hybrid Vector + BM25 Search with Pre-Retrieval Guardrails](docs/adr/ADR-005_hybrid_search_with_preretrieval_guardrails.md)
* [ADR-006: Deterministic 8-Gate Verification Engine Before Generation Acceptance](docs/adr/ADR-006_deterministic_8_gate_verification_engine.md)
* [ADR-007: GraphRAG with Neo4j Ontology for Cross-Policy Impact Paths](docs/adr/ADR-007_graphrag_neo4j_policy_impact_traversals.md)

