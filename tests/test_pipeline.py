"""Tests for the analysis pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from spa.config import load_assistant_registry
from spa.pipeline import PipelineError, run_pipeline


class TestPipeline:
    def test_produces_valid_json(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output, skip_llm=True)
        assert output.exists()
        data = json.loads(output.read_text())
        assert "generated_at" in data
        assert "meta" in data
        assert "prompts" in data
        assert "filters" in data
        assert len(data["prompts"]) > 0

    def test_prompt_entry_structure(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output, skip_llm=True)
        data = json.loads(output.read_text())
        entry = data["prompts"][0]
        assert "assistant_id" in entry
        assert "assistant_name" in entry
        assert "vendor" in entry
        assert "label" in entry
        assert "model" in entry
        assert "metrics" in entry
        assert "tools" in entry
        assert "word_count" in entry["metrics"]

    def test_filters_populated(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output, skip_llm=True)
        data = json.loads(output.read_text())
        expected_count = len(load_assistant_registry())
        assert len(data["filters"]["assistants"]) == expected_count
        assert len(data["filters"]["vendors"]) > 0


class TestPipelineErrors:
    """Error-path tests for pipeline robustness."""

    def test_missing_llm_key_raises_pipeline_error(self, tmp_path: Path, monkeypatch):
        """Pipeline raises PipelineError when LLM_API_KEY is missing."""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        with patch("spa.pipeline.load_dotenv"):  # prevent .env from setting the key
            with pytest.raises(PipelineError, match="LLM_API_KEY"):
                run_pipeline(output_path=tmp_path / "out.json", skip_llm=False)

    def test_missing_prompt_file_is_skipped(self, tmp_path: Path):
        """Prompts referencing nonexistent files are silently skipped."""
        registry = {
            "test-bot": {
                "name": "Test Bot",
                "vendor": "Test",
                "prompts": [
                    {"label": "v1", "path": "nonexistent.txt", "current": True},
                ],
                "tools": [],
            }
        }
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        with (
            patch("spa.pipeline.load_assistant_registry", return_value=registry),
            patch("spa.pipeline.DATA_DIR", data_dir),
        ):
            result = run_pipeline(output_path=tmp_path / "out.json", skip_llm=True)

        # Assistant appears in filters but has no prompts
        assert len(result["filters"]["assistants"]) == 1
        assert len(result["prompts"]) == 0

    def test_corrupt_previous_analysis_is_ignored(self, tmp_path: Path):
        """Corrupt previous analysis JSON doesn't crash the pipeline."""
        prev = tmp_path / "prev.json"
        prev.write_text("{corrupt json!!")

        result = run_pipeline(
            output_path=tmp_path / "out.json",
            skip_llm=True,
            previous_analysis_path=prev,
        )
        assert result is not None
        assert len(result["prompts"]) > 0

    def test_corrupt_tool_file_logs_warning(self, tmp_path: Path):
        """Corrupt tool JSON files are skipped with a warning, not a crash."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        (data_dir / "prompt.txt").write_text("You are a helpful assistant.")
        (data_dir / "tools.json").write_text("{not valid json[[[")

        registry = {
            "test-bot": {
                "name": "Test Bot",
                "vendor": "Test",
                "prompts": [
                    {"label": "v1", "path": "prompt.txt", "current": True},
                ],
                "tools": [
                    {"path": "tools.json", "format": "json"},
                ],
            }
        }

        with (
            patch("spa.pipeline.load_assistant_registry", return_value=registry),
            patch("spa.pipeline.DATA_DIR", data_dir),
        ):
            result = run_pipeline(output_path=tmp_path / "out.json", skip_llm=True)

        # Prompt is still processed; corrupt tools result in 0 tools
        assert len(result["prompts"]) == 1
        assert result["prompts"][0]["tools"]["count"] == 0
