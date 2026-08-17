import hashlib
from typing import Union


def calculate_sha256(content: Union[str, bytes]) -> str:
    """Calculates SHA-256 hash of text or binary content to ensure document immutability."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def verify_content_integrity(content: Union[str, bytes], expected_hash: str) -> bool:
    """Verifies that the content matches its immutable SHA-256 fingerprint."""
    calculated = calculate_sha256(content)
    return calculated.lower() == expected_hash.lower()
