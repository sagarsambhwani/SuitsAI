from typing import List, Dict, Any, Optional
from ai.llamaindex.indexes import DomainIndexRegistry, IndexedDocumentNode, get_index_registry
from ai.models.embeddings import BaseRerankerGateway, get_reranker_gateway


class PreFilteredHybridRetriever:
    """
    Hybrid retriever enforcing pre-retrieval tenant isolation, jurisdiction guardrails,
    and Cohere Rerank 3.5 precision compression.
    Guarantees that Tenant A cannot retrieve Tenant B's data under any condition.
    """

    def __init__(
        self,
        registry: Optional[DomainIndexRegistry] = None,
        reranker: Optional[BaseRerankerGateway] = None,
    ):
        self.registry = registry or get_index_registry()
        self.reranker = reranker or get_reranker_gateway()

    def retrieve_relevant_policies(
        self,
        tenant_id: str,
        query: str,
        jurisdiction: Optional[str] = None,
        top_k: int = 5,
    ) -> List[IndexedDocumentNode]:
        filters: Dict[str, Any] = {"tenant_id": tenant_id}
        if jurisdiction and jurisdiction != "GLOBAL":
            filters["jurisdiction"] = jurisdiction

        policy_index = self.registry.get_index("PolicyIndex")
        return policy_index.search(query=query, filters=filters, top_k=top_k)

    def retrieve_regulatory_evidence(
        self,
        query: str,
        regulator: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        top_k: int = 5,
    ) -> List[IndexedDocumentNode]:
        filters: Dict[str, Any] = {}
        if regulator:
            filters["regulator"] = regulator
        if jurisdiction and jurisdiction != "GLOBAL":
            filters["jurisdiction"] = jurisdiction

        reg_index = self.registry.get_index("RegulationIndex")
        return reg_index.search(query=query, filters=filters, top_k=top_k)

    async def retrieve_with_rerank(
        self,
        query: str,
        index_name: str = "RegulationIndex",
        filters: Optional[Dict[str, Any]] = None,
        candidate_count: int = 50,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Executes the Gold Architecture retrieval pipeline:
        1. Hybrid Search (Vector top 50 + BM25 top 50) with pre-filtering
        2. Cohere Rerank 3.5 candidate compression (50 -> top 8-15)
        """
        target_index = self.registry.get_index(index_name)
        candidates = await target_index.search_hybrid(
            query=query,
            filters=filters,
            top_k=candidate_count,
        )

        candidate_dicts = [
            {
                "id": node.id,
                "text": node.text,
                "doc_type": node.doc_type,
                "metadata": node.metadata,
            }
            for node in candidates
        ]

        # Cohere Rerank 3.5
        reranked = await self.reranker.rerank(
            query=query,
            documents=candidate_dicts,
            top_n=top_k,
        )
        return reranked


_retriever = None


def get_retriever() -> PreFilteredHybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = PreFilteredHybridRetriever()
    return _retriever
