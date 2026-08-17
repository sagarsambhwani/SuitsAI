# Embeddings & Hybrid Retrieval Guide

> **Bedrock Cohere Embed v4 Batching, Cohere Rerank 3.5, & Pre-Filtered Hybrid Search**

---

## 1. Embedding Architecture

SuitsAI decouples **document embedding** (offline ingestion plane) from **query embedding** (online query plane) via [ai/models/embeddings.py](file:///e:/Downloads/VoyagerAI/ai/models/embeddings.py):

```text
DOCUMENTS (Offline Ingestion)              USER QUERIES (Online Query)
Millions of chunks in S3 / SQS              Single incoming compliance query
             │                                            │
             ▼                                            ▼
[Bedrock Cohere Embed v4]                    [Bedrock Cohere Embed v4]
input_type: search_document                  input_type: search_query
Batch size: 32–96 chunks/call                Batch size: 1 vector
             │                                            │
             ▼                                            ▼
   [Vector Database]                        [Pre-Filtered Hybrid Search]
 (pgvector / OpenSearch)                     Vector top 50 + BM25 top 50
             ▲                                            │
             │                                            ▼
             └───────────────◄──────────────────  [Cohere Rerank 3.5]
                                                   50–100 candidate chunks
                                                   ──► top 8–15 evidence
```

---

## 2. Bedrock Cohere Embed v4 Specifications

### Document Embedding (`search_document`)
When indexing new regulations or internal bank policies:
* **`input_type`**: `"search_document"`
* **Batching**: 32–96 chunks per Bedrock API call (configured via `settings.EMBEDDING_BATCH_SIZE`)
* **Truncate**: `"END"`
* **Dimension**: 1024 / 1536 floating-point values

### Query Embedding (`search_query`)
When an end user or automated rule asks a compliance question:
* **`input_type`**: `"search_query"`
* **Payload**: Single text query string returning one normalized vector

```python
# Embedding invocation example
from ai.models.embeddings import get_embedding_gateway

embed_gw = get_embedding_gateway()

# 1. Document batch embedding
doc_vectors = await embed_gw.embed_documents(
    texts=["Section 4.1 Enhanced Due Diligence...", "Section 4.2 API Key Rotation..."],
    input_type="search_document",
)

# 2. Single query embedding
query_vector = await embed_gw.embed_query(
    text="Can we onboard high risk customer without EDD?",
    input_type="search_query",
)
```

---

## 3. Hybrid Search (Vector + BM25)

Legal and banking retrieval requires both **semantic understanding** and **exact keyword matching**:

* **Semantic Search**: "What are the rules for customer verification?" $\longrightarrow$ matches "Customer Due Diligence (CDD)".
* **Exact Keyword Search**: `"Section 4.3.1"`, `"RBI/2026-27/04"`, `"V-CIP"`, `"AML"`.

### Linear Hybrid Combination Formula

$$\text{HybridScore} = \alpha \cdot \text{VectorScore} + (1 - \alpha) \cdot \text{BM25Score}$$

Where:
* $\alpha = 0.7$ (Default vector weight)
* $1 - \alpha = 0.3$ (Default exact token overlap weight)

### Pre-Retrieval Isolation Guardrails

Metadata filters are applied **before or during retrieval**, ensuring that cross-tenant or out-of-jurisdiction documents are never scored or retrieved:

```python
results = await domain_index.search_hybrid(
    query="high-risk PEP onboarding rules",
    filters={
        "tenant_id": "BANK-TENANT-001",
        "jurisdiction": "IN",
        "regulator": "RBI",
    },
    top_k=50,
)
```

---

## 4. Cohere Rerank 3.5 Precision Compression

After hybrid retrieval retrieves the top 50–100 candidate chunks:
1. Candidates are passed to **Cohere Rerank 3.5** (`cohere.rerank-v3-5:0`).
2. The cross-encoder evaluates deep cross-attention between the query and each chunk.
3. The candidates are compressed down to the **top 8–15 high-precision evidence chunks** before entering the LLM prompt.

```python
from ai.llamaindex.retriever import get_retriever

retriever = get_retriever()
top_evidence = await retriever.retrieve_with_rerank(
    query="Can we onboard a high risk customer without EDD?",
    index_name="RegulationIndex",
    filters={"jurisdiction": "IN"},
    candidate_count=50,
    top_k=10,
)
```
