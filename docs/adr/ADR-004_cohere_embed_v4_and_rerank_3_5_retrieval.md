# ADR-004: Cohere Embed v4 Batching & Cohere Rerank 3.5 Two-Stage Retrieval

* **Status**: Accepted
* **Date**: 2026-08-17
* **Deciders**: AI Core Team, Search Infrastructure

---

## Context & Problem Statement
In dense legal corpora, bi-encoder embedding similarity alone often retrieves chunks that are topically related but fail to answer the specific regulatory condition. Passing 50+ chunks directly to the LLM increases token cost, risks the "lost-in-the-middle" attention phenomenon, and slows response generation.

## Decision
We implement a **Two-Stage Retrieval Pipeline**:
1. **Asymmetric Embedding Stage (Cohere Embed v4 / v3 via Bedrock)**:
   * Documents embedded with `input_type="search_document"` in batches of 32–96 chunks.
   * User queries embedded with `input_type="search_query"`.
2. **Cross-Encoder Reranking Stage (Cohere Rerank 3.5 via Bedrock)**:
   * Compresses the top 50–100 hybrid candidates down to the **top 8–15 precision evidence chunks**.

## Consequences
### Positive
* Significantly higher precision and context relevance delivered to the reasoning LLM.
* 70–80% reduction in LLM prompt token consumption.
* Embeddings and reranking available natively within AWS Bedrock in the bank's secure VPC.

### Negative
* Adds a small network hop (~100–180ms) for the reranker invocation during online query processing.
