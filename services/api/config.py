from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "SuitsAI Compliance & Policy Platform"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "super-secret-compliance-platform-key-change-in-production-32bytes!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # PostgreSQL Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./compliance_platform.db"
    POSTGRES_HOST: Optional[str] = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: Optional[str] = "postgres"
    POSTGRES_PASSWORD: Optional[str] = "postgres"
    POSTGRES_DB: Optional[str] = "compliance_db"
    PGVECTOR_DIMENSION: int = 1536

    # Neo4j Knowledge Graph
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    NEO4J_DATABASE: str = "neo4j"
    NEO4J_MOCK_MODE: bool = True  # Allows running standalone with built-in graph engine if Neo4j is offline

    # Redis Cache & Task Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MOCK_MODE: bool = True

    # S3 / Object Storage
    S3_BUCKET_NAME: str = "compliance-platform-lake"
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None  # For LocalStack or MinIO
    LOCAL_STORAGE_DIR: str = "./storage/lake"

    # LLM Settings & Provider Selection
    DEFAULT_LLM_PROVIDER: str = "mock"  # "bedrock", "openai", "azure", "mock"
    BEDROCK_REGION: str = "us-east-1"
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # Embedding & Reranking Settings (Bedrock Cohere / Titan / Mock)
    DEFAULT_EMBEDDING_PROVIDER: str = "mock"  # "bedrock", "openai", "mock"
    BEDROCK_EMBEDDING_MODEL_ID: str = "cohere.embed-multilingual-v3"  # or "cohere.embed-english-v3", "cohere.embed-v4"
    BEDROCK_RERANK_MODEL_ID: str = "cohere.rerank-v3-5:0"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_BATCH_SIZE: int = 96
    
    # Document Ingestion & OCR Settings
    TEXTRACT_ENABLED: bool = False
    OPENSEARCH_HOST: Optional[str] = None
    OPENSEARCH_PORT: int = 443
    OPENSEARCH_INDEX_PREFIX: str = "suits_compliance"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
