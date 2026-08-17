# ADR-005: Hybrid Vector + BM25 Search with Pre-Retrieval Guardrails

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: Security Team, Search Infrastructure

---

## Context & Problem Statement
1. Compliance queries often involve exact alphanumeric references (e.g. `"Section 4.3.1"`, `"RBI/2026-27/04"`, `"V-CIP"`) which vector-only search can miss or score poorly.
2. In multi-tenant banking platforms, letting the LLM filter out unauthorized or foreign-jurisdiction documents after retrieval is a severe compliance violation and data leakage risk.

## Decision
We enforce:
1. **Hybrid Vector + BM25 Scoring**:
   $$\text{Score} = 0.7 \cdot \text{VectorScore} + 0.3 \cdot \text{BM25Score}$$
2. **Pre-Retrieval Metadata Guardrails**:
   * Tenant isolation (`tenant_id`), Jurisdiction (`jurisdiction`), Regulator (`regulator`), and Temporal status (`effective_date`) are applied **before or during index scanning**.

## Consequences
### Positive
* Perfect recall on exact regulatory section numbers and statutory terms.
* Zero possibility of cross-tenant data leakage or applying foreign circulars to local bank policies.

### Negative
* Requires maintaining both vector indices and inverted keyword indices (BM25).
