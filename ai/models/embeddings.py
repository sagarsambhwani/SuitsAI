import json
import math
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from services.api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseEmbeddingGateway(ABC):
    """Abstract interface for high-dimensional document and query embeddings."""

    @abstractmethod
    async def embed_documents(
        self,
        texts: List[str],
        input_type: str = "search_document",
    ) -> List[List[float]]:
        """Batch-embeds a list of document chunks (up to batch_size chunks per request)."""
        pass

    @abstractmethod
    async def embed_query(
        self,
        text: str,
        input_type: str = "search_query",
    ) -> List[float]:
        """Embeds a single query string for semantic similarity retrieval."""
        pass


class MockEmbeddingGateway(BaseEmbeddingGateway):
    """
    Deterministic Mock Embedding Gateway for local development, CI/CD, and offline testing.
    Generates normalized dense vectors based on text token hashing.
    """

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    def _generate_vector(self, text: str) -> List[float]:
        dim = self.dimension
        vec = [0.0] * dim
        words = text.lower().split()
        if not words:
            return vec
        for idx, word in enumerate(words):
            h = hash(word)
            pos = abs(h) % dim
            vec[pos] += 1.0 / (idx + 1)
        # L2-normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec

    async def embed_documents(
        self,
        texts: List[str],
        input_type: str = "search_document",
    ) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]

    async def embed_query(
        self,
        text: str,
        input_type: str = "search_query",
    ) -> List[float]:
        return self._generate_vector(text)


class BedrockCohereEmbeddingGateway(BaseEmbeddingGateway):
    """
    AWS Bedrock Cohere Embed v4 / v3 Integration.
    Supports search_document batching (32-96 chunks per API invocation) and search_query.
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
        batch_size: Optional[int] = None,
    ):
        self.model_id = model_id or settings.BEDROCK_EMBEDDING_MODEL_ID
        self.region = region or settings.BEDROCK_REGION
        self.batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self.fallback = MockEmbeddingGateway(dimension=settings.EMBEDDING_DIMENSION)

    async def embed_documents(
        self,
        texts: List[str],
        input_type: str = "search_document",
    ) -> List[List[float]]:
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=self.region)

            # Chunk texts into batches of up to self.batch_size (default 96)
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                body = {
                    "texts": batch,
                    "input_type": input_type,
                    "truncate": "END",
                }

                response = client.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(body),
                )
                response_body = json.loads(response["body"].read())
                embeddings = response_body.get("embeddings", [])
                all_embeddings.extend(embeddings)

            return all_embeddings
        except Exception as e:
            logger.warning(
                f"[Bedrock Embedding] Invocation failed for {self.model_id}: {e}. "
                f"Falling back to local mock embedding gateway."
            )
            return await self.fallback.embed_documents(texts, input_type)

    async def embed_query(
        self,
        text: str,
        input_type: str = "search_query",
    ) -> List[float]:
        results = await self.embed_documents([text], input_type=input_type)
        return results[0] if results else [0.0] * settings.EMBEDDING_DIMENSION


class BaseRerankerGateway(ABC):
    """Abstract interface for candidate document reranking."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        """Reranks candidate documents against the query and returns top_n scored results."""
        pass


class MockRerankerGateway(BaseRerankerGateway):
    """Deterministic mock reranker scoring documents by keyword overlap."""

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        query_words = set(query.lower().split())
        scored_docs = []
        for idx, doc in enumerate(documents):
            text = doc.get("text", "") or doc.get("content", "")
            doc_words = set(text.lower().split())
            overlap = len(query_words.intersection(doc_words))
            score = round(overlap / max(len(query_words), 1), 4)
            scored_docs.append({
                **doc,
                "relevance_score": score,
                "original_rank": idx,
            })
        scored_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
        return scored_docs[:top_n]


class BedrockCohereRerankerGateway(BaseRerankerGateway):
    """AWS Bedrock / Cohere Rerank 3.5 Integration."""

    def __init__(
        self,
        model_id: Optional[str] = None,
        region: Optional[str] = None,
    ):
        self.model_id = model_id or settings.BEDROCK_RERANK_MODEL_ID
        self.region = region or settings.BEDROCK_REGION
        self.fallback = MockRerankerGateway()

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        if not documents:
            return []

        doc_texts = [d.get("text", "") or d.get("content", "") for d in documents]
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=self.region)
            body = {
                "query": query,
                "documents": doc_texts,
                "top_n": min(top_n, len(documents)),
                "return_documents": False,
            }

            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            results = response_body.get("results", [])

            reranked = []
            for item in results:
                doc_idx = item["index"]
                score = item.get("relevance_score", 0.0)
                original_doc = documents[doc_idx]
                reranked.append({
                    **original_doc,
                    "relevance_score": score,
                    "original_rank": doc_idx,
                })
            return reranked
        except Exception as e:
            logger.warning(
                f"[Bedrock Rerank] Invocation failed for {self.model_id}: {e}. "
                f"Falling back to local mock reranker."
            )
            return await self.fallback.rerank(query, documents, top_n)


def get_embedding_gateway(provider: Optional[str] = None) -> BaseEmbeddingGateway:
    selected = provider or settings.DEFAULT_EMBEDDING_PROVIDER
    if selected == "bedrock":
        return BedrockCohereEmbeddingGateway()
    return MockEmbeddingGateway(dimension=settings.EMBEDDING_DIMENSION)


def get_reranker_gateway(provider: Optional[str] = None) -> BaseRerankerGateway:
    selected = provider or settings.DEFAULT_EMBEDDING_PROVIDER
    if selected == "bedrock":
        return BedrockCohereRerankerGateway()
    return MockRerankerGateway()
