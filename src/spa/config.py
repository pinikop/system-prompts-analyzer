"""Paths, constants, and registry loader."""

from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
WEB_DATA_DIR = ROOT_DIR / "web" / "data"
AGENTS_YAML = ROOT_DIR / "agents.yaml"

# Keywords to search for in prompts (case-insensitive matching done at analysis time)
DIRECTIVE_KEYWORDS = [
    "NEVER",
    "MUST",
    "ALWAYS",
    "DO NOT",
    "IMPORTANT",
    "CRITICAL",
    "REQUIRED",
    "FORBIDDEN",
    "PROHIBITED",
    "MANDATORY",
]

DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-235B-A22B-Instruct-2507"
DEFAULT_LLM_BASE_URL = "https://api.studio.nebius.com/v1/"

TOOL_CATEGORIES = {
    "file_ops": ["read", "write", "edit", "create", "delete", "rename", "move", "copy"],
    "search": ["search", "grep", "find", "glob", "ripgrep"],
    "execution": ["bash", "shell", "terminal", "command", "exec", "run"],
    "web": ["browser", "fetch", "http", "url", "web", "navigate"],
    "git": ["git", "commit", "branch", "push", "pull", "merge", "diff"],
    "ai": ["agent", "subagent", "task", "llm", "model"],
}


def load_assistant_registry() -> dict:
    """Load agents.yaml and return the registry dict."""
    with AGENTS_YAML.open() as f:
        return yaml.safe_load(f)
