# SuitsAI API Reference

> **FastAPI REST Service Specification & Data Transfer Objects (DTOs)**
> Base URL: `http://localhost:8000` (or `https://api.suits.bank.com`)

---

## 1. Authentication & Tenant Headers

All API endpoints require tenant scoping via headers:

| Header | Description | Example |
| :--- | :--- | :--- |
| `X-Tenant-ID` | Required tenant identifier | `BANK-TENANT-001` |
| `Authorization` | Optional Bearer JWT token | `Bearer eyJhbGci...` |

---

## 2. API Endpoints

### A. Document Lake & Ingestion (`/api/v1/documents`)

#### `POST /api/v1/documents/upload`
Uploads and processes any regulatory or bank policy document (PDF, Scans, DOCX, XLSX, PPTX, TXT).

* **Content-Type**: `multipart/form-data`
* **Parameters**:
  * `file`: Binary file stream
  * `code`: String (e.g. `"RBI/2026-27/04"`)
  * `regulator`: String (e.g. `"Reserve Bank of India"`)
  * `jurisdiction`: String (`"IN"`, `"US"`, `"UK"`, `"SG"`, `"GLOBAL"`)
  * `doc_type`: String (`"Circular"`, `"Master Direction"`, `"Law"`, `"Policy"`)
  * `use_ocr`: Boolean (default `false`)

**Response (`200 OK`)**:
```json
{
  "document_id": "DOC-e3b0c44298fc",
  "sha256_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "storage_uri": "s3://compliance-platform-lake/raw/RBI/RBI-2026-27-04/circular.docx",
  "file_type": "docx",
  "parsed_sections_count": 8,
  "extracted_requirements_count": 12,
  "chunks_count": 15,
  "title": "Master Direction on KYC, 2026"
}
```

---

### B. Regulations & Obligations (`/api/v1/regulations`)

#### `POST /api/v1/regulations/ingest`
Ingests a new regulatory notice with raw text or uploaded document reference.

**Request Body**:
```json
{
  "code": "RBI/2026-27/04",
  "title": "Digital Lending & Cyber Security Directive",
  "regulator_name": "Reserve Bank of India",
  "regulator_acronym": "RBI",
  "jurisdiction": "IN",
  "doc_type": "Circular",
  "publication_date": "2026-07-01T00:00:00Z",
  "effective_date": "2026-07-01T00:00:00Z",
  "raw_text": "Section 1.1: All API tokens shall be rotated every 90 days."
}
```

#### `GET /api/v1/regulations`
Lists all active regulations, filtered optionally by `?jurisdiction=IN`.

---

### C. Compliance Assessment & Gap Engine (`/api/v1/compliance`)

#### `POST /api/v1/compliance/analyze`
Triggers the full LangGraph reasoning pipeline + 8-Gate verification engine.

**Request Body**:
```json
{
  "regulation_id": "REG-UUID-1234",
  "async_mode": false,
  "mode": "standard"
}
```

**Response (`200 OK`)**:
```json
{
  "assessment_id": "ASSESS-UUID-5678",
  "run_id": "RUN-20260817-001",
  "tenant_id": "BANK-TENANT-001",
  "regulation_id": "REG-UUID-1234",
  "regulation_code": "RBI/2026-27/04",
  "status": "PENDING_REVIEW",
  "mode": "standard",
  "confidence_score": 1.0,
  "total_requirements": 4,
  "gaps_detected": 1,
  "all_gates_passed": true,
  "verification_scorecard": {
    "overall_passed": true,
    "confidence_score": 1.0,
    "passed_gates_count": 8,
    "total_gates": 8,
    "gates": {
      "evidence_gate": { "passed": true, "status": "PASS", "details": "SHA-256 matched." },
      "temporal_gate": { "passed": true, "status": "PASS", "details": "Active version." },
      "jurisdiction_gate": { "passed": true, "status": "PASS", "details": "Jurisdiction IN matched." },
      "applicability_gate": { "passed": true, "status": "PASS", "details": "Applies to Commercial Banks." },
      "coverage_gate": { "passed": true, "status": "PASS", "details": "100% requirements mapped." },
      "exception_preservation_gate": { "passed": true, "status": "PASS", "details": "Exceptions preserved." },
      "citation_gate": { "passed": true, "status": "PASS", "details": "Verbatim quote confirmed." },
      "contradiction_gate": { "passed": true, "status": "PASS", "details": "No verb inversions." }
    }
  },
  "changes": [
    {
      "policy_code": "POL-INF-001",
      "clause_number": "Clause 4.2.1",
      "change_type": "AMENDMENT",
      "original_text": "API keys shall be rotated every 180 days.",
      "proposed_text": "All API keys and credentials shall be rotated at least every 90 calendar days.",
      "justification": "Aligned with circular Section 4.1 requiring 90-day rotation.",
      "citations": [
        {
          "doc": "RBI/2026-27/04",
          "section": "Section 4.1",
          "quote": "cryptographic keys and API tokens are rotated at intervals not exceeding 90 days",
          "page": 1
        }
      ],
      "claim_lineages": [
        {
          "claim_text": "All API keys and credentials shall be rotated at least every 90 calendar days.",
          "source_verbatim_quote": "cryptographic keys and API tokens are rotated at intervals not exceeding 90 days",
          "page_number": 1,
          "verification_status": "VERIFIED",
          "similarity_score": 1.0
        }
      ],
      "citation_verified": true,
      "coverage_verified": true,
      "exceptions_preserved": true,
      "status": "PENDING_REVIEW"
    }
  ],
  "created_at": "2026-08-17T14:15:00Z"
}
```

#### `GET /api/v1/compliance/replay/{run_id}`
Retrieves the frozen point-in-time state snapshot (`ComplianceRunSnapshot`) for auditor inspection.

---

### D. Approvals & Human Review Gateway (`/api/v1/approvals`)

#### `POST /api/v1/approvals/review`
Submits a compliance officer's decision on proposed policy amendments.

**Request Body**:
```json
{
  "policy_change_id": "CHG-UUID-9012",
  "decision": "APPROVE",
  "reviewer_comments": "Verified against latest RBI guidelines. Ready for publishing."
}
```

---

### E. Health & Monitoring (`/health`)

#### `GET /health`
Returns service, database, graph, and embedding health status.

**Response (`200 OK`)**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-08-17T14:15:00Z",
  "database": "connected",
  "embedding_provider": "mock",
  "llm_provider": "mock"
}
```
