# ADR-001: Two-Plane Architecture for Banking Compliance Document RAG

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: Architecture Team, Compliance Engineering

---

## Context & Problem Statement
In banking and financial compliance, document corpora span thousands of regulatory circulars, master directions, statutes, internal bank SOPs, and audit logs. Processing these complex documents synchronously during user queries leads to high latency, API timeouts, excessive cost, and unacceptable non-deterministic compliance determinations.

## Decision
We establish a strict **Two-Plane Architecture**:

1. **Offline Ingestion / Indexing Plane**:
   * Asynchronous, event-driven ingestion using S3, SQS, and background workers.
   * Calculates SHA-256 fingerprints, performs layout extraction (PDF/Word/Excel/Textract), extracts obligations/conditions/exceptions, creates hierarchical chunks, batch-embeds vectors via Cohere Embed v4 (`search_document`), and synchronizes the Neo4j Knowledge Graph.
2. **Online Query / Reasoning Plane**:
   * Low-latency query path executing pre-retrieval tenant/jurisdiction filtering, hybrid vector + BM25 search, Cohere Rerank 3.5 precision compression, Bedrock LLM reasoning, and 8-Gate verification.

## Consequences
### Positive
* Ingestion scales independently from user query traffic.
* Heavy OCR and document parsing never block user queries.
* Complete point-in-time corpus versioning ensures reproducibility.

### Negative
* Requires asynchronous queue infrastructure (SQS / Redis) for background processing.
