"""Integration tests for pipeline output and dashboard data invariants."""

import json

import pytest

from spa.pipeline import run_pipeline

EXPECTED_ASSISTANTS = 9
EXPECTED_CURRENT = 16
EXPECTED_TOTAL = 26
EXPECTED_MODELS = {
    "claude-sonnet-4",
    "gemini-2.5-pro",
    "gpt-4.1",
    "gpt-4o",
    "gpt-5",
    "gpt-5-mini",
}
MULTI_MODEL_ASSISTANTS = {"vscode-copilot": 6, "augment": 2, "amp": 2}
REQUIRED_PROMPT_KEYS = {
    "assistant_id",
    "assistant_name",
    "vendor",
    "label",
    "model",
    "is_current",
    "metrics",
    "tools",
    "llm_analysis",
}
REQUIRED_METRIC_KEYS = {
    "word_count",
    "line_count",
    "char_count",
    "section_count",
    "directive_count",
    "example_count",
    "directive_density",
    "format_type",
}


@pytest.fixture(scope="module")
def pipeline_output(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run pipeline once, share result across all tests in this module."""
    output = tmp_path_factory.mktemp("data") / "analysis.json"
    run_pipeline(output_path=output, skip_llm=True)
    return json.loads(output.read_text())


class TestOutputSchema:
    """Verify top-level JSON structure."""

    def test_top_level_keys(self, pipeline_output: dict) -> None:
        assert set(pipeline_output.keys()) == {
            "generated_at",
            "cache_info",
            "meta",
            "prompts",
            "comparisons",
            "filters",
        }

    def test_output_includes_cache_info(self, pipeline_output: dict) -> None:
        """Output JSON includes cache_info metadata."""
        assert "cache_info" in pipeline_output
        cache_info = pipeline_output["cache_info"]
        assert "data_source_commit" in cache_info
        assert "file_hashes" in cache_info
        assert isinstance(cache_info["file_hashes"], dict)

    def test_meta_counts(self, pipeline_output: dict) -> None:
        meta = pipeline_output["meta"]
        assert meta["assistant_count"] == EXPECTED_ASSISTANTS
        assert meta["prompt_count"] == EXPECTED_TOTAL

    def test_filter_lists(self, pipeline_output: dict) -> None:
        filters = pipeline_output["filters"]
        assert len(filters["assistants"]) == EXPECTED_ASSISTANTS
        assert sorted(filters["models"]) == sorted(EXPECTED_MODELS)
        assert len(filters["vendors"]) > 0

    def test_assistant_filter_entries_have_id_and_name(self, pipeline_output: dict) -> None:
        for assistant in pipeline_output["filters"]["assistants"]:
            assert "id" in assistant
            assert "name" in assistant


class TestPromptEntries:
    """Verify each prompt entry has correct structure and valid data."""

    def test_total_prompt_count(self, pipeline_output: dict) -> None:
        assert len(pipeline_output["prompts"]) == EXPECTED_TOTAL

    def test_required_keys_present(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            missing = REQUIRED_PROMPT_KEYS - set(entry.keys())
            assert not missing, f"{entry['assistant_id']}/{entry['label']}: missing {missing}"

    def test_required_metric_keys(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            missing = REQUIRED_METRIC_KEYS - set(entry["metrics"].keys())
            assert not missing, f"{entry['assistant_id']}: missing metrics {missing}"

    def test_tools_structure(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            tools = entry["tools"]
            assert "count" in tools
            assert "names" in tools
            assert isinstance(tools["names"], list)
            assert isinstance(tools["count"], int)

    def test_no_null_assistant_ids(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            assert entry["assistant_id"] is not None
            assert entry["assistant_id"] != ""

    def test_word_counts_positive(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            assert entry["metrics"]["word_count"] > 0, (
                f"{entry['assistant_id']}/{entry['label']} has 0 words"
            )


class TestCurrentFlag:
    """Verify is_current filtering produces expected dashboard data."""

    def test_current_prompt_count(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        assert len(current) == EXPECTED_CURRENT

    def test_every_assistant_has_at_least_one_current(self, pipeline_output: dict) -> None:
        current_assistants = {
            p["assistant_id"] for p in pipeline_output["prompts"] if p["is_current"]
        }
        all_assistants = {p["assistant_id"] for p in pipeline_output["prompts"]}
        missing = all_assistants - current_assistants
        assert not missing, f"Assistants with no current prompt: {missing}"

    def test_multi_model_assistants_current_counts(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        for assistant_id, expected_count in MULTI_MODEL_ASSISTANTS.items():
            assistant_current = [p for p in current if p["assistant_id"] == assistant_id]
            assert len(assistant_current) == expected_count, (
                f"{assistant_id}: expected {expected_count} current, got {len(assistant_current)}"
            )

    def test_multi_model_assistants_have_model_tags(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        for assistant_id in MULTI_MODEL_ASSISTANTS:
            assistant_current = [p for p in current if p["assistant_id"] == assistant_id]
            for p in assistant_current:
                assert p["model"] is not None, (
                    f"{assistant_id}/{p['label']}: multi-model assistant missing model tag"
                )

    def test_single_model_assistants_have_one_current(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        single_assistants = {p["assistant_id"] for p in pipeline_output["prompts"]} - set(
            MULTI_MODEL_ASSISTANTS.keys()
        )
        for assistant_id in single_assistants:
            assistant_current = [p for p in current if p["assistant_id"] == assistant_id]
            assert len(assistant_current) == 1, (
                f"{assistant_id}: expected 1 current, got {len(assistant_current)}"
            )


class TestFilterLogic:
    """Verify cascading filter invariants match what the dashboard expects."""

    def test_models_only_from_current_prompts(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        current_models = {p["model"] for p in current if p["model"]}
        filter_models = set(pipeline_output["filters"]["models"])
        # Every filter model must exist in at least one current prompt
        assert filter_models <= current_models, (
            f"Filter models not in current: {filter_models - current_models}"
        )

    def test_all_current_models_in_filters(self, pipeline_output: dict) -> None:
        current = [p for p in pipeline_output["prompts"] if p["is_current"]]
        current_models = {p["model"] for p in current if p["model"]}
        filter_models = set(pipeline_output["filters"]["models"])
        assert current_models <= filter_models, (
            f"Current models missing from filters: {current_models - filter_models}"
        )

    def test_assistant_filter_ids_match_prompts(self, pipeline_output: dict) -> None:
        filter_ids = {a["id"] for a in pipeline_output["filters"]["assistants"]}
        prompt_ids = {p["assistant_id"] for p in pipeline_output["prompts"]}
        assert filter_ids == prompt_ids


class TestLlmSkipped:
    """Verify LLM fields when --skip-llm is used."""

    def test_llm_analysis_is_none(self, pipeline_output: dict) -> None:
        for entry in pipeline_output["prompts"]:
            assert entry["llm_analysis"] is None, (
                f"{entry['assistant_id']}/{entry['label']}: "
                "llm_analysis should be None when skipped"
            )

    def test_comparisons_empty(self, pipeline_output: dict) -> None:
        assert pipeline_output["comparisons"] == []

    def test_llm_model_is_none(self, pipeline_output: dict) -> None:
        assert pipeline_output["meta"]["llm_model"] is None
