import math
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from ai.models.embeddings import BaseEmbeddingGateway, get_embedding_gateway


class IndexedDocumentNode(BaseModel):
    id: str
    text: str
    doc_type: str  # REGULATION, REQUIREMENT, POLICY_CLAUSE, CONTROL, HIERARCHICAL_CHUNK
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    bm25_tokens: Optional[List[str]] = None


class ScoredDocumentNode(BaseModel):
    node: IndexedDocumentNode
    hybrid_score: float
    vector_score: float
    bm25_score: float


class DomainIndex:
    """
    Hybrid Vector + BM25 domain index for compliance and banking regulatory documents.
    Supports pre-retrieval metadata filtering (Tenant, Jurisdiction, Regulator, Effective Date).
    """

    def __init__(
        self,
        name: str,
        embedding_gateway: Optional[BaseEmbeddingGateway] = None,
        hybrid_alpha: float = 0.7,  # 0.7 Vector, 0.3 BM25
    ):
        self.name = name
        self.nodes: Dict[str, IndexedDocumentNode] = {}
        self.embedding_gateway = embedding_gateway or get_embedding_gateway()
        self.hybrid_alpha = hybrid_alpha

    def add_node(self, node: IndexedDocumentNode):
        if not node.bm25_tokens:
            node.bm25_tokens = self._tokenize(node.text)
        self.nodes[node.id] = node

    async def add_nodes_batch(self, nodes: List[IndexedDocumentNode]):
        """Batch-embeds chunks using Cohere Embed v4 (up to 96 per request) and indexes them."""
        unembedded = [n for n in nodes if not n.embedding]
        if unembedded:
            texts = [n.text for n in unembedded]
            embeddings = await self.embedding_gateway.embed_documents(texts, input_type="search_document")
            for node, emb in zip(unembedded, embeddings):
                node.embedding = emb

        for node in nodes:
            self.add_node(node)

    async def search_hybrid(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
    ) -> List[IndexedDocumentNode]:
        """Runs Hybrid Vector + BM25 search with pre-retrieval metadata filtering."""
        candidates = list(self.nodes.values())

        # 1. Apply strict pre-retrieval metadata filters (Tenant, Jurisdiction, Regulator, Temporal)
        if filters:
            filtered = []
            for node in candidates:
                match = True
                for k, v in filters.items():
                    if k in node.metadata and node.metadata[k] != v:
                        match = False
                        break
                if match:
                    filtered.append(node)
            candidates = filtered

        if not candidates:
            return []

        # 2. Embed Query (search_query mode)
        query_embed = await self.embedding_gateway.embed_query(query, input_type="search_query")
        query_tokens = set(self._tokenize(query))

        # 3. Calculate Vector & BM25 Scores
        scored: List[ScoredDocumentNode] = []
        for node in candidates:
            # Vector cosine similarity
            v_score = 0.0
            if node.embedding:
                v_score = self._cosine_similarity(query_embed, node.embedding)
            else:
                # Fallback to local deterministic generator if node has no precomputed vector
                local_emb = self._simple_embed(node.text)
                v_score = self._cosine_similarity(query_embed, local_emb)

            # BM25 / Keyword overlap score
            doc_tokens = node.bm25_tokens or self._tokenize(node.text)
            overlap = len(query_tokens.intersection(doc_tokens))
            b_score = round(overlap / max(len(query_tokens), 1), 4)

            # Hybrid linear combination
            h_score = round((self.hybrid_alpha * v_score) + ((1.0 - self.hybrid_alpha) * b_score), 4)

            scored.append(
                ScoredDocumentNode(
                    node=node,
                    hybrid_score=h_score,
                    vector_score=round(v_score, 4),
                    bm25_score=b_score,
                )
            )

        scored.sort(key=lambda x: x.hybrid_score, reverse=True)
        return [item.node for item in scored[:top_k]]

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
    ) -> List[IndexedDocumentNode]:
        """Synchronous search wrapper using fast deterministic local vectors for backwards compatibility."""
        query_embed = self._simple_embed(query)
        query_tokens = set(self._tokenize(query))
        candidates = list(self.nodes.values())

        if filters:
            filtered = []
            for node in candidates:
                match = True
                for k, v in filters.items():
                    if k in node.metadata and node.metadata[k] != v:
                        match = False
                        break
                if match:
                    filtered.append(node)
            candidates = filtered

        scored = []
        for node in candidates:
            emb = node.embedding or self._simple_embed(node.text)
            v_score = self._cosine_similarity(query_embed, emb)
            doc_tokens = node.bm25_tokens or self._tokenize(node.text)
            b_score = len(query_tokens.intersection(doc_tokens)) / max(len(query_tokens), 1)
            h_score = (self.hybrid_alpha * v_score) + ((1.0 - self.hybrid_alpha) * b_score)
            scored.append((h_score, node))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [w.lower() for w in re.findall(r"\w+", text) if len(w) > 2]

    def _simple_embed(self, text: str, dim: int = 64) -> List[float]:
        vec = [0.0] * dim
        words = text.lower().split()
        for idx, word in enumerate(words):
            h = hash(word)
            pos = abs(h) % dim
            vec[pos] += 1.0 / (idx + 1)
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        return float(dot)


class DomainIndexRegistry:
    """Registry for domain-specific indexes."""

    def __init__(self):
        self.regulation_index = DomainIndex("RegulationIndex")
        self.requirement_index = DomainIndex("RequirementIndex")
        self.policy_index = DomainIndex("PolicyIndex")
        self.control_index = DomainIndex("ControlIndex")

    def get_index(self, index_name: str) -> DomainIndex:
        if index_name == "RegulationIndex":
            return self.regulation_index
        elif index_name == "RequirementIndex":
            return self.requirement_index
        elif index_name == "PolicyIndex":
            return self.policy_index
        elif index_name == "ControlIndex":
            return self.control_index
        return self.regulation_index


_index_registry = None


def get_index_registry() -> DomainIndexRegistry:
    global _index_registry
    if _index_registry is None:
        _index_registry = DomainIndexRegistry()
    return _index_registry
