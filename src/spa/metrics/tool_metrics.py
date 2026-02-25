"""Tool metrics computation."""

from spa.config import TOOL_CATEGORIES
from spa.parsers.base import ToolDefinition


def compute_tool_metrics(tools: list[ToolDefinition]) -> dict:
    """Compute metrics for a list of tool definitions."""
    names = sorted({t.name for t in tools})
    sources: dict[str, int] = {}
    for t in tools:
        sources[t.source] = sources.get(t.source, 0) + 1

    categories: dict[str, list[str]] = {}
    for tool in tools:
        text = f"{tool.name} {tool.description}".lower()
        for cat, keywords in TOOL_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                categories.setdefault(cat, [])
                if tool.name not in categories[cat]:
                    categories[cat].append(tool.name)

    return {
        "count": len(names),
        "names": names,
        "categories": categories,
        "sources": sources,
    }
