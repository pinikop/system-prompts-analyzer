"""Classify prompt sections into semantic categories."""

from spa.parsers.base import PromptSection

_CATEGORIES: dict[str, list[str]] = {
    "identity": ["identity", "you are", "your name", "role", "persona", "who you are"],
    "tone": ["tone", "style", "concise", "verbos", "communication", "response format"],
    "safety": ["safety", "security", "never", "prohibited", "forbidden", "harm",
               "injection", "malicious", "privacy"],
    "tools": ["tool", "function", "command", "parameter", "schema", "input_schema"],
    "workflow": ["git", "commit", "pull request", "deploy", "ci", "branch", "merge",
                 "code review", "pr"],
    "examples": ["example", "e.g.", "sample", "demonstration", "here is"],
}


def classify_section(section: PromptSection) -> str:
    """Classify a single section into a semantic category."""
    name_lower = section.name.lower()
    content_preview = section.content[:200].lower()
    text = f"{name_lower} {content_preview}"

    best_category = "other"
    best_score = 0

    for category, keywords in _CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def classify_sections(sections: list[PromptSection]) -> dict[str, int]:
    """Classify all sections and return counts by category."""
    counts: dict[str, int] = {}
    for section in sections:
        cat = classify_section(section)
        counts[cat] = counts.get(cat, 0) + 1
    return counts
