"""Tests for data source sync and file hashing utilities."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from spa.data_source import (
    compute_file_hash,
    get_local_commit,
    get_remote_commit,
    sync_data,
)

FAKE_SHA = "abc123def456789012345678901234567890abcd"
FAKE_SHA2 = "def456789012345678901234567890abcdabc123"
REPO = "x1xhlol/system-prompts-and-models-of-ai-tools"


def test_compute_file_hash(tmp_path: Path) -> None:
    """File hash is deterministic SHA256."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")

    hash1 = compute_file_hash(file_path)
    hash2 = compute_file_hash(file_path)

    assert hash1 == hash2
    assert hash1.startswith("sha256:")
    assert len(hash1) == 71  # "sha256:" + 64 hex chars


class TestGetLocalCommit:
    def test_returns_sha(self, tmp_path: Path) -> None:
        with patch("spa.data_source.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=f"{FAKE_SHA}\n", stderr=""
            )
            result = get_local_commit(tmp_path)

        assert result == FAKE_SHA
        mock_run.assert_called_once()

    def test_returns_none_when_not_git_repo(self, tmp_path: Path) -> None:
        with patch(
            "spa.data_source.subprocess.run",
            side_effect=subprocess.CalledProcessError(128, "git"),
        ):
            assert get_local_commit(tmp_path) is None


class TestGetRemoteCommit:
    def test_parses_github_api_response(self) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"sha": FAKE_SHA}).encode()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("spa.data_source.urllib.request.urlopen", return_value=mock_response):
            result = get_remote_commit(REPO)

        assert result == FAKE_SHA


class TestSyncData:
    def test_clones_when_missing(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        with (
            patch("spa.data_source.get_local_commit", side_effect=[None, FAKE_SHA]),
            patch("spa.data_source.clone_data") as mock_clone,
        ):
            result = sync_data(data_dir, REPO)

        mock_clone.assert_called_once_with(data_dir, REPO)
        assert result == FAKE_SHA

    def test_skips_when_up_to_date(self, tmp_path: Path) -> None:
        with (
            patch("spa.data_source.get_local_commit", return_value=FAKE_SHA),
            patch("spa.data_source.get_remote_commit", return_value=FAKE_SHA),
            patch("spa.data_source.update_data") as mock_update,
        ):
            result = sync_data(tmp_path, REPO)

        mock_update.assert_not_called()
        assert result == FAKE_SHA

    def test_fetches_when_behind(self, tmp_path: Path) -> None:
        with (
            patch("spa.data_source.get_local_commit", side_effect=[FAKE_SHA, FAKE_SHA2]),
            patch("spa.data_source.get_remote_commit", return_value=FAKE_SHA2),
            patch("spa.data_source.update_data") as mock_update,
        ):
            result = sync_data(tmp_path, REPO)

        mock_update.assert_called_once_with(tmp_path)
        assert result == FAKE_SHA2

    def test_skip_update_flag(self, tmp_path: Path) -> None:
        with (
            patch("spa.data_source.get_local_commit", return_value=FAKE_SHA),
            patch("spa.data_source.get_remote_commit") as mock_remote,
        ):
            result = sync_data(tmp_path, REPO, skip_update=True)

        mock_remote.assert_not_called()
        assert result == FAKE_SHA

    def test_network_failure_continues(self, tmp_path: Path) -> None:
        with (
            patch("spa.data_source.get_local_commit", return_value=FAKE_SHA),
            patch(
                "spa.data_source.get_remote_commit",
                side_effect=URLError("connection refused"),
            ),
        ):
            result = sync_data(tmp_path, REPO)

        assert result == FAKE_SHA
