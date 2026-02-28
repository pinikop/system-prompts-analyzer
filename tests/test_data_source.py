"""Tests for GitHub data source and caching."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from spa.data_source import compute_file_hash, load_cache_metadata, save_cache_metadata


def test_compute_file_hash(tmp_path: Path) -> None:
    """File hash is deterministic SHA256."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")

    hash1 = compute_file_hash(file_path)
    hash2 = compute_file_hash(file_path)

    assert hash1 == hash2
    assert hash1.startswith("sha256:")
    assert len(hash1) == 71  # "sha256:" + 64 hex chars


def test_load_cache_metadata_missing_file(tmp_path: Path) -> None:
    """Returns empty dict when cache file doesn't exist."""
    cache_file = tmp_path / ".spa-data-source.json"
    result = load_cache_metadata(cache_file)
    assert result == {}


def test_save_and_load_cache_metadata(tmp_path: Path) -> None:
    """Cache metadata round-trips correctly."""
    cache_file = tmp_path / ".spa-data-source.json"
    metadata = {
        "upstream_repo": "test/repo",
        "commit": "abc123",
        "file_hashes": {"file1.txt": "sha256:..."},
    }

    save_cache_metadata(cache_file, metadata)
    loaded = load_cache_metadata(cache_file)

    assert loaded == metadata
