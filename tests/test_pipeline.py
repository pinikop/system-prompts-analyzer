"""Tests for the analysis pipeline."""

import json
from pathlib import Path

from spa.pipeline import run_pipeline


class TestPipeline:
    def test_produces_valid_json(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert "generated_at" in data
        assert "meta" in data
        assert "prompts" in data
        assert "filters" in data
        assert len(data["prompts"]) > 0

    def test_prompt_entry_structure(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        data = json.loads(output.read_text())
        entry = data["prompts"][0]
        assert "agent_id" in entry
        assert "agent_name" in entry
        assert "vendor" in entry
        assert "label" in entry
        assert "model" in entry
        assert "metrics" in entry
        assert "tools" in entry
        assert "word_count" in entry["metrics"]

    def test_filters_populated(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        data = json.loads(output.read_text())
        assert len(data["filters"]["agents"]) == 9
        assert len(data["filters"]["vendors"]) > 0
