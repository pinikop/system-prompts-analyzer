"""LLM-powered thematic analysis of coding assistant system prompts."""

import logging
import os
from dataclasses import dataclass

from spa.config import DEFAULT_LLM_BASE_URL
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


def _build_prompt(raw_text: str, tool_names: list[str], assistant_name: str) -> str:
    """Build LLM prompt for analyzing a coding assistant's system prompt."""
    tools = "\n".join(f"- {t}" for t in tool_names) if tool_names else "No tools defined."

    # Get schema description for field validation
    schema_desc = AssistantAnalysis.model_json_schema()

    return f"""Analyze this system prompt for the coding assistant "{assistant_name}".

Extract ALL fields below. Both operational and thematic sections are required.

**Operational Instructions:**
- permission_rules: When does it ask permission vs. act autonomously? Extract 3-5 rules.
- workflow_approach: What methodology does it follow (TDD, debugging process, planning)?
- safety_rules: What is it prohibited from doing? What must it always/never do? 3-5 rules.
- tool_philosophy: How should it use tools? Any preferences or constraints?

**Thematic Analysis:**
- identity: {schema_desc["properties"]["identity"]["description"]}
- tone: {schema_desc["properties"]["tone"]["description"]}
- personality: {schema_desc["properties"]["personality"]["description"]}
- behavioral_rules: {schema_desc["properties"]["behavioral_rules"]["description"]}
- unique_features: {schema_desc["properties"]["unique_features"]["description"]}
- coding_philosophy: {schema_desc["properties"]["coding_philosophy"]["description"]}
- safety_emphasis: {schema_desc["properties"]["safety_emphasis"]["description"]}
  Options: {", ".join(schema_desc["properties"]["safety_emphasis"]["enum"])}
- safety_details: {schema_desc["properties"]["safety_details"]["description"]}
- autonomy_level: {schema_desc["properties"]["autonomy_level"]["description"]}
  Options: {", ".join(schema_desc["properties"]["autonomy_level"]["enum"])}
- error_handling: {schema_desc["properties"]["error_handling"]["description"]}

**Available tools:**
{tools}

**System prompt to analyze:**
{raw_text}

Return valid JSON matching the AssistantAnalysis schema.
IMPORTANT: Include ALL fields from both Operational Instructions and Thematic Analysis sections.
"""


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
    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_LLM_BASE_URL

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
