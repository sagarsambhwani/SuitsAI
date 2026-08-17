# ADR-003: Hierarchical Semantic-Structural Chunking with Obligation Metadata

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: AI Core Team, Compliance Engineering

---

## Context & Problem Statement
Naive fixed-character or fixed-token chunking (e.g. splitting every 500 characters) frequently bisects legal obligations, placing the condition ("if transaction > USD 10,000") in one chunk and the mandate ("must trigger automated AML monitoring") in another, or completely dropping statutory exemptions ("except when customer is central government entity").

## Decision
We enforce **Hierarchical Semantic + Structural Chunking**:
1. **Atomic Preservation**: Legal clauses are kept intact whenever possible within a target window of 400–700 tokens (350–500 words).
2. **Context Window Overlap**: When a section exceeds 500 words, a sliding window with 10–15% overlap (~40 words) is applied.
3. **Hierarchy Propagation**: Each chunk carries its structural lineage: $\text{Document} \longrightarrow \text{Chapter} \longrightarrow \text{Section} \longrightarrow \text{Clause}$.
4. **Structured Metadata Tagging**: Every chunk is enriched with `obligation_type` (`MANDATORY`, `CONDITIONAL`, `PROHIBITED`), `conditions`, `exceptions`, `risk_category`, `jurisdiction`, `regulator`, and `effective_date`.

## Consequences
### Positive
* Eliminates out-of-context retrieval where conditions are separated from obligations.
* Enables precise filtering by risk category and obligation type.

### Negative
* Chunk sizes vary slightly based on natural section boundaries rather than rigid character counts.
