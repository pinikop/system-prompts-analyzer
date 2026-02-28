"""GitHub data source with caching and change detection."""

import hashlib
import json
from pathlib import Path
from typing import Any

import requests


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents.

    Returns:
        Hash string in format "sha256:hexdigest"
    """
    content = file_path.read_bytes()
    hash_obj = hashlib.sha256(content)
    return f"sha256:{hash_obj.hexdigest()}"


def load_cache_metadata(cache_file: Path) -> dict[str, Any]:
    """Load cache metadata from JSON file.

    Returns empty dict if file doesn't exist or is invalid.
    """
    if not cache_file.exists():
        return {}

    try:
        return json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache_metadata(cache_file: Path, metadata: dict[str, Any]) -> None:
    """Save cache metadata to JSON file."""
    cache_file.write_text(json.dumps(metadata, indent=2))


def get_upstream_commit(repo: str) -> str:
    """Get latest commit SHA from GitHub repo.

    Args:
        repo: Repository in format "owner/name"

    Returns:
        Latest commit SHA

    Raises:
        requests.HTTPError: If API request fails
    """
    url = f"https://api.github.com/repos/{repo}/commits/HEAD"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()["sha"]
