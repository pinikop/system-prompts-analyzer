"""File hashing utilities for cache change detection."""

import hashlib
from pathlib import Path


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents.

    Returns:
        Hash string in format "sha256:hexdigest"
    """
    content = file_path.read_bytes()
    hash_obj = hashlib.sha256(content)
    return f"sha256:{hash_obj.hexdigest()}"
