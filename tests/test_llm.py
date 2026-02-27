"""Tests for LLM analysis schemas, prompt building, and rankings."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from spa.llm.analyzer import _build_prompt, _parse_response
from spa.llm.rankings import compute_rankings
from spa.llm.schemas import AssistantAnalysis

VALID_ANALYSIS = {
    "identity": "A helpful coding assistant focused on productivity.",
    "tone": ["concise", "direct", "helpful"],
    "personality": "Professional and efficient, prefers action over discussion.",
    "behavioral_rules": [
        "Always read files before editing",
        "Never modify code without permission",
        "Use dedicated tools over shell commands",
        "Confirm destructive actions",
        "Keep responses concise",
    ],
    "unique_features": [
        "Integrated terminal access",
        "Multi-file editing",
        "Git workflow support",
    ],
    "coding_philosophy": "Write minimal, correct code. Avoid over-engineering.",
    "safety_emphasis": "high",
    "safety_details": "Extensive safety rules around destructive actions and data handling.",
    "autonomy_level": "medium",
    "error_handling": "Investigates root causes before applying fixes.",
}


class TestAssistantAnalysisSchema:
    def test_valid_input(self) -> None:
        analysis = AssistantAnalysis(**VALID_ANALYSIS)
        assert analysis.safety_emphasis == "high"
        assert len(analysis.tone) == 3

    def test_invalid_safety_level(self) -> None:
        data = {**VALID_ANALYSIS, "safety_emphasis": "extreme"}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)

    def test_invalid_autonomy_level(self) -> None:
        data = {**VALID_ANALYSIS, "autonomy_level": "extreme"}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)

    def test_too_few_tone_descriptors(self) -> None:
        data = {**VALID_ANALYSIS, "tone": ["concise"]}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)

    def test_too_many_tone_descriptors(self) -> None:
        data = {**VALID_ANALYSIS, "tone": ["a", "b", "c", "d", "e", "f"]}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)

    def test_too_few_behavioral_rules(self) -> None:
        data = {**VALID_ANALYSIS, "behavioral_rules": ["rule1"]}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)

    def test_serialization_roundtrip(self) -> None:
        analysis = AssistantAnalysis(**VALID_ANALYSIS)
        dumped = analysis.model_dump()
        restored = AssistantAnalysis(**dumped)
        assert restored == analysis


class TestPromptBuilding:
    def test_build_prompt_includes_assistant_name(self) -> None:
        prompt = _build_prompt("some text", ["tool_a", "tool_b"], "TestBot")
        assert "TestBot" in prompt
        assert "some text" in prompt
        assert "- tool_a" in prompt
        assert "- tool_b" in prompt

    def test_build_prompt_no_tools(self) -> None:
        prompt = _build_prompt("some text", [], "TestBot")
        assert "No tools defined." in prompt

    def test_build_prompt_includes_field_descriptions(self) -> None:
        prompt = _build_prompt("text", [], "Bot")
        assert "safety_emphasis" in prompt
        assert "autonomy_level" in prompt
        assert '"low", "medium", "high"' in prompt


class TestParseResponse:
    def test_parse_valid_json(self) -> None:
        content = json.dumps(VALID_ANALYSIS)
        result = _parse_response(content)
        assert isinstance(result, AssistantAnalysis)
        assert result.safety_emphasis == "high"

    def test_parse_json_with_markdown_fences(self) -> None:
        content = f"```json\n{json.dumps(VALID_ANALYSIS)}\n```"
        result = _parse_response(content)
        assert isinstance(result, AssistantAnalysis)

    def test_parse_invalid_json_raises(self) -> None:
        with pytest.raises(Exception):
            _parse_response("not valid json")


class TestComputeRankings:
    @pytest.fixture()
    def sample_data(self) -> tuple[dict[str, AssistantAnalysis], list[dict]]:
        analyses = {
            "alpha::v1": AssistantAnalysis(**VALID_ANALYSIS),
            "beta::v1": AssistantAnalysis(
                **{**VALID_ANALYSIS, "safety_emphasis": "low", "autonomy_level": "high"}
            ),
        }
        prompts = [
            {
                "assistant_id": "alpha",
                "label": "v1",
                "is_current": True,
                "metrics": {"word_count": 5000, "directive_density": 12.5},
                "tools": {"count": 20},
            },
            {
                "assistant_id": "beta",
                "label": "v1",
                "is_current": True,
                "metrics": {"word_count": 2000, "directive_density": 5.0},
                "tools": {"count": 8},
            },
        ]
        return analyses, prompts

    def test_returns_five_dimensions(self, sample_data) -> None:
        analyses, prompts = sample_data
        rankings = compute_rankings(analyses, prompts)
        assert len(rankings) == 5
        dims = {r["dimension"] for r in rankings}
        assert dims == {
            "Safety Emphasis",
            "Autonomy Level",
            "Verbosity",
            "Tool Richness",
            "Directive Density",
        }

    def test_safety_values(self, sample_data) -> None:
        analyses, prompts = sample_data
        rankings = compute_rankings(analyses, prompts)
        safety = next(r for r in rankings if r["dimension"] == "Safety Emphasis")
        assert safety["rankings"]["alpha::v1"] == "high"
        assert safety["rankings"]["beta::v1"] == "low"

    def test_verbosity_values(self, sample_data) -> None:
        analyses, prompts = sample_data
        rankings = compute_rankings(analyses, prompts)
        verbosity = next(r for r in rankings if r["dimension"] == "Verbosity")
        assert verbosity["rankings"]["alpha::v1"] == 5000
        assert verbosity["rankings"]["beta::v1"] == 2000

    def test_empty_analyses(self) -> None:
        rankings = compute_rankings({}, [])
        assert len(rankings) == 5
        for r in rankings:
            assert r["rankings"] == {}


class TestAnalyzeAssistantIntegration:
    """Test analyze_assistant with mocked litellm."""

    def test_successful_analysis(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            from spa.llm.analyzer import analyze_assistant

            result = analyze_assistant(
                raw_text="You are a helpful assistant.",
                tool_names=["read", "write"],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(result, AssistantAnalysis)
        assert result.safety_emphasis == "high"
        mock_completion.assert_called_once()

    def test_retry_on_validation_failure(self) -> None:
        bad_response = MagicMock()
        bad_response.choices = [MagicMock(message=MagicMock(content='{"invalid": true}'))]
        good_response = MagicMock()
        good_response.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]

        with patch(
            "litellm.completion", side_effect=[bad_response, good_response]
        ) as mock_completion:
            from spa.llm.analyzer import analyze_assistant

            result = analyze_assistant(
                raw_text="prompt",
                tool_names=[],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(result, AssistantAnalysis)
        assert mock_completion.call_count == 2
