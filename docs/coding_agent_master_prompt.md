# SuitsAI: Master Coding-Agent Implementation Prompt (v4)

> **Autonomous Coding-Agent Implementation Specification for Institutional Banking Compliance Intelligence**
>
> *Use this prompt to instruct any AI coding agent (e.g. Antigravity, Claude Code, Cursor, Copilot Workspace) to implement or expand the SuitsAI enterprise compliance platform across all 11 core banking governance modules.*

---

## 📋 System Context & Environment Metadata

* **Repository**: `https://github.com/sagarsambhwani/SuitsAI.git` (Branch: `main`)
* **Operating System**: Windows / Linux
* **Python Runtime**: Python 3.10+ inside virtual environment (`.\.venv\Scripts\python.exe` / `pytest`)
* **Core Technology Stack**:
  * **API & Web**: FastAPI (Async), Pydantic v2, Uvicorn, Vanilla CSS/JS client
  * **Relational & Vector Database**: PostgreSQL 16 with `pgvector` (via SQLAlchemy 2.0 Async + `asyncpg` / `aiosqlite`)
  * **Knowledge Graph**: Neo4j Enterprise (Cypher multi-hop graph ontology)
  * **Document Lake**: Amazon S3 (WORM-compliant layout-aware object store with SHA-256 checksums)
  * **Orchestration**: `LangGraph` (`StateGraph` over typed `ComplianceState` with checkpointing)
  * **Retrieval & Reranking**: `LlamaIndex` (`DomainIndex` hybrid cosine $0.7$ + BM25 $0.3$) + AWS Bedrock Cohere Rerank 3.5
  * **Foundation Models**: AWS Bedrock Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`) and Claude 3.5 Haiku (`anthropic.claude-3-5-haiku-20241022-v1:0`)

---

## 🎯 Task Objective

Implement and extend the enterprise banking compliance system to provide a full end-to-end, defensible regulatory lifecycle engine covering **all 11 critical institutional compliance dimensions** while preserving the existing **Two-Plane Architecture**, **LangGraph StateGraph**, **Neo4j GraphRAG**, and **8-Gate Deterministic Verification Engine**.

---

## 🧱 Module Implementation Specifications (11 Dimensions)

### 1. Obligation Model & Deontic Logic Parsing
* **File**: `services/ingestion/parser.py` & `database/postgres/models.py`
* **Requirements**:
  * Parse raw statutory circulars into strongly typed `ExtractedRequirement` models.
  * Classify modal deontic verbs:
    * `MANDATORY` (*"shall"*, *"must"*, *"is required to"*)
    * `PROHIBITIVE` (*"shall not"*, *"must not"*, *"prohibited from"*, *"is not permitted"*)
    * `PERMISSIVE` (*"may"*, *"can at its discretion"*)
    * `CONDITIONAL` (*"if assets > 500M, then shall..."*)
  * Extract prescriptive actions, compliance deadlines, and penalty clauses.

### 2. Applicability Assessment Engine
* **File**: `services/compliance/rules_engine.py`
* **Requirements**:
  * Filter regulatory circulars against the tenant's entity profile:
    * Entity Types: `Commercial Bank`, `NBFC`, `Digital Lending Entity`, `Payment Aggregator`, `Foreign Branch`.
    * Asset Thresholds: Balance sheet size, Tier-1 capital limits, retail vs wholesale classification.
    * Geographic Bounds: `IN`, `US`, `SG`, `UK`, `EU`, `GLOBAL`.
  * Return deterministic applicability verdicts before executing LLM reasoning.

### 3. Control Library & KRI Mapping
* **File**: `services/graph/ontology.py` & `database/postgres/models.py`
* **Requirements**:
  * Model internal bank controls in PostgreSQL and Neo4j:
    * Control Types: `PREVENTIVE`, `DETECTIVE`, `CORRECTIVE`.
    * Frequency: `REAL_TIME`, `DAILY`, `MONTHLY`, `QUARTERLY`, `ANNUAL`.
    * Key Risk Indicators (KRIs) and automated test procedures.
  * Connect controls to policy clauses: `(:PolicyClause)-[:ENFORCED_BY]->(:Control)`.

### 4. GraphRAG Multi-Hop Impact Assessment
* **File**: `services/graph/client.py` & `ai/langgraph/nodes.py`
* **Requirements**:
  * Execute recursive Cypher traversals:
    ```cypher
    MATCH (reg:Regulation {code: $code})-[:CONTAINS]->(req:Requirement)
    OPTIONAL MATCH (req)-[:IMPACTS]->(clause:PolicyClause)<-[:CONTAINS]-(pol:Policy)
    OPTIONAL MATCH (clause)-[:ENFORCED_BY]->(ctrl:Control)
    OPTIONAL MATCH (pol)-[:GOVERNS]->(bu:BusinessUnit)
    RETURN req, pol, clause, ctrl, bu
    ```
  * Compute downstream impact paths and affected business units in $<15\text{ms}$.

### 5. Risk & Materiality Scoring Matrix
* **File**: `services/compliance/rules_engine.py`
* **Requirements**:
  * Compute multidimensional risk scores ($1 - 5$ scale):
    * Regulatory Fine Risk (Statutory penalties, license revocation).
    * Operational Risk (System changes, IT migration effort).
    * Reputational Risk (Customer data exposure, KYC breach).
  * Assign overall materiality rating: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.

### 6. Remediation Planning & Redline Generator
* **File**: `ai/prompts/policy_drafting.py` & `ai/langgraph/nodes.py`
* **Requirements**:
  * Generate sentence-level redline diffs (`original_text` vs `proposed_text`).
  * Include clear legal justifications citing specific circular sections.
  * Formulate time-bound operational action plans with department ownership.

### 7. Evidence & Testing Engine (8-Gate Verification)
* **File**: `services/compliance/verification.py`
* **Requirements**:
  * Execute the 8-Gate verification scorecard on all AI proposals:
    1. `Evidence Gate`: SHA-256 checksum match with S3 lake.
    2. `Temporal Gate`: `effective_date <= NOW() < superseded_date`.
    3. `Jurisdiction Gate`: Jurisdiction alignment.
    4. `Applicability Gate`: Entity scope verification.
    5. `100% Coverage Gate`: Zero unmapped requirements.
    6. `Exception Preservation Gate`: Zero dropped statutory exceptions.
    7. `Citation Evidence Gate`: Verbatim substring evidence match.
    8. `Contradiction Gate`: No inverted obligation modal verbs.

### 8. Temporal Versioning & Supersession Lifecycle
* **File**: `database/postgres/models.py` & `services/api/routers/regulations.py`
* **Requirements**:
  * Track regulatory version history: `version_number`, `effective_date`, `publication_date`, `superseded_date`.
  * Support point-in-time historical compliance auditing: *"Was our policy compliant on March 15, 2025?"*
  * Create `(:Regulation)-[:SUPERSEDES]->(:Regulation)` graph relationships.

### 9. Provenance & Sentence-Level Claim Lineage
* **File**: `database/postgres/models.py` (`ClaimLineage`)
* **Requirements**:
  * Link every single AI-drafted sentence to an immutable `ClaimLineage` record:
    * `source_document_sha256`
    * `page_number`
    * `paragraph_number`
    * `verbatim_source_quote`
    * `similarity_score`

### 10. Statutory Exception & Exemption Preserver
* **File**: `services/compliance/verification.py`
* **Requirements**:
  * Detect and extract statutory exceptions (*"except when...", "provided that...", "exempted entities include..."*).
  * Ensure proposed policy redlines explicitly preserve these exemptions, blocking over-compliance.

### 11. Dual-Control Maker-Checker Governance (4-Eyes Principle)
* **File**: `services/api/routers/approvals.py`
* **Requirements**:
  * Enforce Maker-Checker workflow:
    1. Maker (Compliance Analyst) submits proposal with justification.
    2. Checker (Chief Compliance Officer) reviews and authorizes.
  * **Strict Separation of Duty**: Reject self-approval ($\text{Maker} \neq \text{Checker}$) with `403 Forbidden`.
  * Compute SHA-256 digital signature of approved text and publish immutable `PolicyVersion`.

---

## 🔒 Strict Engineering Rules & Constraints

1. **Virtual Environment**: Always run and test code using the virtual environment (`.\.venv\Scripts\python.exe` and `.\.venv\Scripts\pytest.exe`).
2. **Defensibility**: The LLM must NEVER be the unverified source of truth. All generative output must pass the 8-Gate verification engine.
3. **Tenant Isolation**: Apply pre-retrieval filtering (`WHERE tenant_id = :tenant_id`) at the database index layer before vector similarity scoring.
4. **Testing**: Every added feature must include automated unit/integration tests in `tests/` with 100% pass rate.
5. **No Regressions**: Ensure all existing test suites pass cleanly.

---

## 🚀 Step-by-Step Implementation Instructions for the Agent

1. **Inspect Existing Code**: View `services/compliance/verification.py`, `ai/langgraph/workflow.py`, `services/graph/ontology.py`, and `database/postgres/models.py`.
2. **Implement Missing Fields & Nodes**: Extend models, LangGraph nodes, and API routers according to the 11-dimension specification.
3. **Execute Test Suite**: Run `.\.venv\Scripts\pytest.exe -v` to ensure zero regressions.
4. **Document & Commit**: Create ADRs for significant architectural changes and commit files cleanly to `main`.
