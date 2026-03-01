"""Tests for file hashing utilities."""

from pathlib import Path

from spa.data_source import compute_file_hash


def test_compute_file_hash(tmp_path: Path) -> None:
    """File hash is deterministic SHA256."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")

    hash1 = compute_file_hash(file_path)
    hash2 = compute_file_hash(file_path)

    assert hash1 == hash2
    assert hash1.startswith("sha256:")
    assert len(hash1) == 71  # "sha256:" + 64 hex chars
