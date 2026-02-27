"""Derive cross-assistant comparison rankings from structured analysis data."""

from spa.llm.schemas import AssistantAnalysis

SAFETY_ORDER = {"low": 0, "medium": 1, "high": 2, "very_high": 3}
AUTONOMY_ORDER = {"low": 0, "medium": 1, "high": 2}


def compute_rankings(
    analyses: dict[str, AssistantAnalysis],
    prompts: list[dict],
) -> list[dict]:
    """Compute ranking dimensions across all analyzed coding assistants.

    Args:
        analyses: Map of prompt key -> AssistantAnalysis for current prompts.
        prompts: Full prompt entries from the pipeline (with metrics/tools).

    Returns:
        List of ranking dimensions, each with ranked values per prompt key.
    """
    # Build lookup for metrics by prompt key
    metrics_by_key: dict[str, dict] = {}
    for p in prompts:
        key = f"{p['assistant_id']}::{p['label']}"
        if key in analyses:
            metrics_by_key[key] = p

    dimensions: list[dict] = []

    # Safety emphasis (LLM-derived)
    dimensions.append(
        {
            "dimension": "Safety Emphasis",
            "rankings": {key: analysis.safety_emphasis for key, analysis in analyses.items()},
        }
    )

    # Autonomy level (LLM-derived)
    dimensions.append(
        {
            "dimension": "Autonomy Level",
            "rankings": {key: analysis.autonomy_level for key, analysis in analyses.items()},
        }
    )

    # Verbosity (metrics-derived)
    dimensions.append(
        {
            "dimension": "Verbosity",
            "rankings": {
                key: metrics_by_key[key]["metrics"]["word_count"]
                for key in analyses
                if key in metrics_by_key
            },
        }
    )

    # Tool richness (metrics-derived)
    dimensions.append(
        {
            "dimension": "Tool Richness",
            "rankings": {
                key: metrics_by_key[key]["tools"]["count"]
                for key in analyses
                if key in metrics_by_key
            },
        }
    )

    # Directive density (metrics-derived)
    dimensions.append(
        {
            "dimension": "Directive Density",
            "rankings": {
                key: metrics_by_key[key]["metrics"]["directive_density"]
                for key in analyses
                if key in metrics_by_key
            },
        }
    )

    return dimensions
