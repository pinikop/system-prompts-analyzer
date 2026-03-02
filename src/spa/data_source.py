"""Data source sync and file hashing utilities."""

import hashlib
import json
import logging
import subprocess
import urllib.request
from pathlib import Path
from urllib.error import URLError

logger = logging.getLogger(__name__)


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA256 hash of file contents.

    Returns:
        Hash string in format "sha256:hexdigest"
    """
    content = file_path.read_bytes()
    hash_obj = hashlib.sha256(content)
    return f"sha256:{hash_obj.hexdigest()}"


def get_local_commit(data_dir: Path) -> str | None:
    """Get the current HEAD commit SHA of the local data repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(data_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_remote_commit(repo: str) -> str:
    """Fetch the latest commit SHA for the main branch via GitHub API."""
    url = f"https://api.github.com/repos/{repo}/commits/main"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
    return data["sha"]


def clone_data(data_dir: Path, repo: str) -> None:
    """Shallow-clone the upstream data repo."""
    url = f"https://github.com/{repo}.git"
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(data_dir)],
        check=True,
    )


def update_data(data_dir: Path) -> None:
    """Fetch and reset local data repo to latest upstream main."""
    subprocess.run(
        ["git", "-C", str(data_dir), "fetch", "origin"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(data_dir), "reset", "--hard", "origin/main"],
        check=True,
    )


def sync_data(data_dir: Path, repo: str, *, skip_update: bool = False) -> str:
    """Ensure data/ exists and is up to date. Returns the HEAD commit SHA."""
    local_commit = get_local_commit(data_dir)

    # No local repo - clone it
    if local_commit is None:
        logger.info("Cloning data from %s...", repo)
        clone_data(data_dir, repo)
        commit = get_local_commit(data_dir)
        assert commit is not None  # noqa: S101
        logger.info("Cloned data at %s", commit[:12])
        return commit

    if skip_update:
        logger.debug("Skipping upstream check (--skip-update)")
        return local_commit

    # Check remote for updates
    try:
        remote_commit = get_remote_commit(repo)
    except (URLError, OSError, KeyError, json.JSONDecodeError) as e:
        logger.warning("Could not check upstream (%s), using local data", e)
        return local_commit

    if remote_commit == local_commit:
        logger.info("Data is up to date (%s)", local_commit[:12])
        return local_commit

    logger.info("Updating data %s -> %s...", local_commit[:12], remote_commit[:12])
    try:
        update_data(data_dir)
    except subprocess.CalledProcessError as e:
        logger.warning("Update failed (%s), using local data", e)
        return local_commit

    new_commit = get_local_commit(data_dir)
    return new_commit or local_commit
