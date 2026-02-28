"""Tests for incremental processing with LLM cache."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from spa.pipeline import run_pipeline

FAKE_LLM_ANALYSIS = {
    "identity": "Cached assistant",
    "tone": ["cached", "helpful", "concise"],
    "personality": "Efficient and direct.",
    "behavioral_rules": ["rule1", "rule2", "rule3", "rule4", "rule5"],
    "unique_features": ["feature1", "feature2", "feature3"],
    "coding_philosophy": "Write clean code.",
    "safety_emphasis": "medium",
    "safety_details": "Avoids harmful actions.",
    "autonomy_level": "medium",
    "error_handling": "Reports errors clearly.",
}


def _make_previous_analysis(tmp_path: Path) -> Path:
    """Run pipeline once to get real hashes, inject fake LLM analyses."""
    first_run = tmp_path / "first.json"
    run_pipeline(output_path=first_run, skip_llm=True)
    data = json.loads(first_run.read_text())

    for entry in data["prompts"]:
        if entry.get("is_current"):
            entry["llm_analysis"] = FAKE_LLM_ANALYSIS

    first_run.write_text(json.dumps(data))
    return first_run


def test_cache_hit_skips_analyze_assistant(tmp_path: Path) -> None:
    """When all file hashes match, analyze_assistant is never called."""
    previous = _make_previous_analysis(tmp_path)
    output = tmp_path / "second.json"

    with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}):
        with patch("spa.llm.analyzer.analyze_assistant") as mock_analyze:
            run_pipeline(
                output_path=output,
                skip_llm=False,
                previous_analysis_path=previous,
            )

    mock_analyze.assert_not_called()


def test_cache_hit_preserves_llm_analysis(tmp_path: Path) -> None:
    """Cached LLM analysis is attached to prompt entries in output."""
    previous = _make_previous_analysis(tmp_path)
    output = tmp_path / "second.json"

    with patch.dict(os.environ, {"LLM_API_KEY": "test-key"}):
        with patch("spa.llm.analyzer.analyze_assistant"):
            result = run_pipeline(
                output_path=output,
                skip_llm=False,
                previous_analysis_path=previous,
            )

    current = [p for p in result["prompts"] if p.get("is_current")]
    assert len(current) > 0
    for entry in current:
        assert entry["llm_analysis"] is not None
        assert entry["llm_analysis"]["identity"] == "Cached assistant"


def test_no_previous_analysis_runs_normally(tmp_path: Path) -> None:
    """Without previous_analysis_path, pipeline skips cache and runs normally."""
    output = tmp_path / "out.json"
    result = run_pipeline(output_path=output, skip_llm=True)

    assert result is not None
    assert "cache_info" in result
