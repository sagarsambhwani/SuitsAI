import os
import logging
from typing import Optional, Union, BinaryIO
from services.api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DocumentLakeStorage:
    """
    Manages the S3 Document Lake structure:
    s3://compliance-platform/
        raw/tenant/ or raw/regulator/
        normalized/tenant/
        parsed/tenant/
        embeddings/tenant/
        exports/tenant/
    """

    def __init__(self):
        self.bucket = settings.S3_BUCKET_NAME
        self.local_dir = os.path.abspath(settings.LOCAL_STORAGE_DIR)
        os.makedirs(self.local_dir, exist_ok=True)
        self._s3_client = None
        self._init_client()

    def _init_client(self):
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                import boto3
                self._s3_client = boto3.client(
                    "s3",
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    endpoint_url=settings.S3_ENDPOINT_URL,
                )
                logger.info("Initialized S3 client for Document Lake")
            except Exception as e:
                logger.warning(f"Failed to connect to S3: {e}. Using local storage directory.")

    def store_document(
        self,
        folder: str,  # "raw", "normalized", "parsed", "embeddings", "exports"
        entity_path: str,  # e.g., "RBI/2026-04" or "BANK-001/AML_Policy"
        filename: str,
        content: Union[str, bytes],
    ) -> str:
        """Stores a document immutably in the lake and returns its storage URI."""
        key = f"{folder}/{entity_path}/{filename}".replace("\\", "/")
        
        # Always write to local storage lake directory as resilient cache / fallback
        local_target_path = os.path.join(self.local_dir, key)
        os.makedirs(os.path.dirname(local_target_path), exist_ok=True)
        
        mode = "w" if isinstance(content, str) else "wb"
        encoding = "utf-8" if isinstance(content, str) else None
        with open(local_target_path, mode, encoding=encoding) as f:
            f.write(content)

        # Also upload to S3 if configured
        if self._s3_client:
            try:
                body = content.encode("utf-8") if isinstance(content, str) else content
                self._s3_client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=body,
                )
                return f"s3://{self.bucket}/{key}"
            except Exception as e:
                logger.error(f"S3 upload error for {key}: {e}")

        return f"file://{local_target_path}"

    def retrieve_document(self, storage_uri: str) -> Optional[bytes]:
        """Retrieves document bytes from S3 or local lake."""
        if storage_uri.startswith("file://"):
            local_path = storage_uri.replace("file://", "")
            if os.path.exists(local_path):
                with open(local_path, "rb") as f:
                    return f.read()
        elif storage_uri.startswith("s3://") and self._s3_client:
            try:
                path = storage_uri.replace(f"s3://{self.bucket}/", "")
                response = self._s3_client.get_object(Bucket=self.bucket, Key=path)
                return response["Body"].read()
            except Exception as e:
                logger.error(f"Error fetching from S3 ({storage_uri}): {e}")

        return None


_storage = None


def get_document_storage() -> DocumentLakeStorage:
    global _storage
    if _storage is None:
        _storage = DocumentLakeStorage()
    return _storage
