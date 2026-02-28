"""Tests for LLM analysis schemas, prompt building, and rankings."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from spa.llm.analyzer import TokenUsage, _build_prompt, _parse_response
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
    # Operational fields
    "permission_rules": [
        "Ask before destructive operations",
        "Confirm before creating PRs",
        "Act autonomously for local edits and tests",
    ],
    "workflow_approach": "Strict TDD: write failing test, implement minimal code, refactor.",
    "safety_rules": [
        "Never commit credentials or secrets",
        "Never use --force flags without explicit permission",
        "Always verify tests pass before claiming completion",
    ],
    "tool_philosophy": "Prefer dedicated tools (Read/Edit) over shell commands (cat/sed).",
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

    def test_operational_fields_required(self) -> None:
        """Operational fields are required and validated."""
        data = {**VALID_ANALYSIS}  # Start with valid base

        # Add operational fields
        data["permission_rules"] = [
            "Ask before destructive ops",
            "Confirm before PRs",
            "Act autonomously for edits",
        ]
        data["workflow_approach"] = "Strict TDD with test-first discipline."
        data["safety_rules"] = [
            "Never commit secrets",
            "Never force-push",
            "Always verify tests",
        ]
        data["tool_philosophy"] = "Prefer Read/Edit over shell commands."

        analysis = AssistantAnalysis(**data)
        assert len(analysis.permission_rules) == 3
        assert analysis.workflow_approach.startswith("Strict TDD")
        assert len(analysis.safety_rules) == 3
        assert "Read/Edit" in analysis.tool_philosophy

    def test_permission_rules_length_validation(self) -> None:
        """permission_rules must have 3-5 items."""
        data = {**VALID_ANALYSIS, "permission_rules": ["only one"]}
        with pytest.raises(ValidationError):
            AssistantAnalysis(**data)


class TestTokenUsage:
    def test_addition(self) -> None:
        usage1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage2 = TokenUsage(prompt_tokens=200, completion_tokens=75, total_tokens=275)
        total = usage1 + usage2
        assert total.prompt_tokens == 300
        assert total.completion_tokens == 125
        assert total.total_tokens == 425

    def test_to_dict(self) -> None:
        usage = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        result = usage.to_dict()
        assert result == {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}

    def test_from_response_with_usage(self) -> None:
        mock_response = MagicMock()
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        usage = TokenUsage.from_response(mock_response)
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150

    def test_from_response_without_usage(self) -> None:
        mock_response = MagicMock()
        mock_response.usage = None
        usage = TokenUsage.from_response(mock_response)
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0


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
        assert "low, medium, high" in prompt

    def test_prompt_includes_operational_instructions(self) -> None:
        """Prompt requests extraction of operational fields."""
        prompt = _build_prompt("some text", ["tool_a"], "TestBot")

        # Verify operational instructions are present
        assert "permission_rules" in prompt
        assert "workflow_approach" in prompt
        assert "safety_rules" in prompt
        assert "tool_philosophy" in prompt
        assert "When does it ask permission vs. act autonomously" in prompt


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
        mock_response.usage = None

        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            from spa.llm.analyzer import analyze_assistant

            analysis, usage = analyze_assistant(
                raw_text="You are a helpful assistant.",
                tool_names=["read", "write"],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(analysis, AssistantAnalysis)
        assert analysis.safety_emphasis == "high"
        assert isinstance(usage, dict)
        mock_completion.assert_called_once()

    def test_retry_on_validation_failure(self) -> None:
        bad_response = MagicMock()
        bad_response.choices = [MagicMock(message=MagicMock(content='{"invalid": true}'))]
        bad_response.usage = None
        good_response = MagicMock()
        good_response.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]
        good_response.usage = None

        with patch(
            "litellm.completion", side_effect=[bad_response, good_response]
        ) as mock_completion:
            from spa.llm.analyzer import analyze_assistant

            analysis, usage = analyze_assistant(
                raw_text="prompt",
                tool_names=[],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(analysis, AssistantAnalysis)
        assert isinstance(usage, dict)
        assert mock_completion.call_count == 2

    def test_returns_token_usage(self) -> None:
        """analyze_assistant should return token usage from the API response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]
        mock_response.usage = MagicMock(
            prompt_tokens=1500,
            completion_tokens=250,
            total_tokens=1750,
        )

        with patch("litellm.completion", return_value=mock_response):
            from spa.llm.analyzer import analyze_assistant

            analysis, usage = analyze_assistant(
                raw_text="You are a helpful assistant.",
                tool_names=["read", "write"],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(analysis, AssistantAnalysis)
        assert usage["prompt_tokens"] == 1500
        assert usage["completion_tokens"] == 250
        assert usage["total_tokens"] == 1750

    def test_accumulates_token_usage_on_retry(self) -> None:
        """Token usage should include both attempts when retrying."""
        bad_response = MagicMock()
        bad_response.choices = [MagicMock(message=MagicMock(content='{"invalid": true}'))]
        bad_response.usage = MagicMock(
            prompt_tokens=1000,
            completion_tokens=100,
            total_tokens=1100,
        )

        good_response = MagicMock()
        good_response.choices = [MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))]
        good_response.usage = MagicMock(
            prompt_tokens=1200,
            completion_tokens=150,
            total_tokens=1350,
        )

        with patch("litellm.completion", side_effect=[bad_response, good_response]):
            from spa.llm.analyzer import analyze_assistant

            analysis, usage = analyze_assistant(
                raw_text="prompt",
                tool_names=[],
                assistant_name="TestBot",
                model="test-model",
            )

        assert isinstance(analysis, AssistantAnalysis)
        # Should sum tokens from both attempts
        assert usage["prompt_tokens"] == 2200  # 1000 + 1200
        assert usage["completion_tokens"] == 250  # 100 + 150
        assert usage["total_tokens"] == 2450  # 1100 + 1350


class TestBaseUrlConfiguration:
    def test_uses_default_when_env_not_set(self) -> None:
        """Uses DEFAULT_LLM_BASE_URL when env var not set."""
        from spa.config import DEFAULT_LLM_BASE_URL

        with patch.dict(os.environ, {}, clear=True):
            with patch("litellm.completion") as mock_completion:
                mock_completion.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                    usage=None,
                )

                from spa.llm.analyzer import analyze_assistant

                analyze_assistant(
                    raw_text="test",
                    tool_names=[],
                    assistant_name="TestBot",
                    model="test-model",
                )

                call_kwargs = mock_completion.call_args[1]
                assert call_kwargs["api_base"] == DEFAULT_LLM_BASE_URL

    def test_env_var_overrides_default(self) -> None:
        """LLM_BASE_URL env var overrides DEFAULT_LLM_BASE_URL."""
        custom_url = "https://api.openai.com/v1/"

        with patch.dict(os.environ, {"LLM_BASE_URL": custom_url}):
            with patch("litellm.completion") as mock_completion:
                mock_completion.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                    usage=None,
                )

                from spa.llm.analyzer import analyze_assistant

                analyze_assistant(
                    raw_text="test",
                    tool_names=[],
                    assistant_name="TestBot",
                    model="test-model",
                )

                call_kwargs = mock_completion.call_args[1]
                assert call_kwargs["api_base"] == custom_url
