"""LLM-powered thematic analysis of coding assistant system prompts."""

import logging
import os
from dataclasses import dataclass

from spa.llm.schemas import AssistantAnalysis

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage statistics from LLM API calls."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def to_dict(self) -> dict[str, int]:
        """Convert to dict for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }

    @classmethod
    def from_response(cls, response) -> "TokenUsage":
        """Extract token usage from litellm response."""
        if hasattr(response, "usage") and response.usage:
            return cls(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
        return cls(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage objects."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


PROMPT_TEMPLATE = """\
You are analyzing the system prompt of an AI coding assistant called "{assistant_name}".

Below is the full system prompt text, followed by a list of tools available to this assistant.

<system_prompt>
{raw_text}
</system_prompt>

<tools>
{tool_list}
</tools>

Analyze this system prompt and return a JSON object with exactly these fields:

- "identity" (string): 1-2 sentence identity statement for this assistant
- "tone" (array of 3-5 strings): tone descriptors, e.g. ["concise", "direct", "cautious"]
- "personality" (string): 1-2 sentence personality summary
- "behavioral_rules" (array of 5-10 strings): key behavioral rules extracted from the prompt
- "unique_features" (array of 3-5 strings): features that distinguish this coding assistant
- "coding_philosophy" (string): 1-2 sentence summary of coding approach
- "safety_emphasis" (string): one of "low", "medium", "high", "very_high"
- "safety_details" (string): 1-2 sentence description of safety approach
- "autonomy_level" (string): one of "low", "medium", "high"
- "error_handling" (string): 1-2 sentence approach to errors

Return ONLY a valid JSON object with these fields. No markdown fences, no extra text."""


def _build_prompt(raw_text: str, tool_names: list[str], assistant_name: str) -> str:
    """Build the analysis prompt from template."""
    if tool_names:
        tool_list = "\n".join(f"- {name}" for name in tool_names)
    else:
        tool_list = "No tools defined."
    return PROMPT_TEMPLATE.format(
        assistant_name=assistant_name,
        raw_text=raw_text,
        tool_list=tool_list,
    )


def _parse_response(content: str) -> AssistantAnalysis:
    """Parse LLM response text into AssistantAnalysis, stripping markdown fences if present."""
    text = content.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return AssistantAnalysis.model_validate_json(text)


def analyze_assistant(
    raw_text: str,
    tool_names: list[str],
    assistant_name: str,
    model: str,
) -> tuple[AssistantAnalysis, dict[str, int]]:
    """Run LLM analysis on a single coding assistant's system prompt.

    Retries once on validation failure with a corrective prompt.

    Returns:
        Tuple of (analysis, token_usage_dict) where token_usage_dict contains:
        - prompt_tokens: input tokens used
        - completion_tokens: output tokens generated
        - total_tokens: sum of both
    """
    import litellm

    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    prompt = _build_prompt(raw_text, tool_names, assistant_name)

    kwargs: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["api_base"] = base_url

    # Track cumulative token usage
    total_usage = TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)

    # First attempt
    logger.info("Analyzing %s with %s...", assistant_name, model)
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    # Accumulate token usage from first attempt
    total_usage = total_usage + TokenUsage.from_response(response)

    try:
        return _parse_response(content), total_usage.to_dict()
    except Exception as first_error:
        error_msg = str(first_error)
        logger.warning("First parse failed for %s: %s. Retrying...", assistant_name, error_msg)

    # Retry with corrective prompt
    kwargs["messages"].append({"role": "assistant", "content": content})
    kwargs["messages"].append(
        {
            "role": "user",
            "content": (
                f"Your response failed validation: {error_msg}\n"
                "Please fix the JSON and return ONLY valid JSON matching the schema."
            ),
        }
    )

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    # Accumulate token usage from retry
    total_usage = total_usage + TokenUsage.from_response(response)

    return _parse_response(content), total_usage.to_dict()
