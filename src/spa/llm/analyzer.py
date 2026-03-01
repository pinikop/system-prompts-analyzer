"""LLM-powered thematic analysis of coding assistant system prompts."""

import logging
import os
import time
from dataclasses import dataclass

import litellm

from spa.config import DEFAULT_LLM_BASE_URL
from spa.llm.schemas import AssistantAnalysis

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM analysis errors."""


class AuthenticationError(LLMError):
    """API key or authentication failed."""


class NetworkError(LLMError):
    """Network/connectivity issue."""


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


def _classify_llm_error(e: Exception) -> Exception:
    """Classify an LLM API exception into AuthenticationError, NetworkError, or pass through."""
    error_str = str(e).lower()
    if "api key" in error_str or "unauthorized" in error_str or "authentication" in error_str:
        return AuthenticationError(f"API key invalid or missing: {e}")
    if "timeout" in error_str or "connection" in error_str or "network" in error_str:
        return NetworkError(f"Network error: {e}")
    return e


def _build_prompt(raw_text: str, tool_names: list[str], assistant_name: str) -> str:
    """Build LLM prompt for analyzing a coding assistant's system prompt."""
    tools = "\n".join(f"- {t}" for t in tool_names) if tool_names else "No tools defined."

    return f"""Analyze this system prompt for the coding assistant "{assistant_name}".

Return a FLAT JSON object with ALL 14 fields at the top level.
Do NOT nest fields under section keys.

Required JSON structure (all fields at top level):
{{
  "identity": "1-2 sentence identity statement",
  "tone": ["3-5 tone descriptors, e.g. concise, direct, cautious"],
  "personality": "1-2 sentence personality summary",
  "behavioral_rules": ["5-10 key behavioral rules extracted from the prompt"],
  "unique_features": ["3-5 features that distinguish this coding assistant"],
  "coding_philosophy": "1-2 sentence summary of coding approach",
  "safety_emphasis": "low|medium|high|very_high",
  "safety_details": "1-2 sentence description of safety approach",
  "autonomy_level": "low|medium|high",
  "error_handling": "1-2 sentence approach to errors",
  "permission_rules": ["3-5 rules about when it asks permission vs. acts autonomously"],
  "workflow_approach": "1-2 sentences on methodology (TDD, debugging, planning)",
  "safety_rules": ["3-5 key safety constraints or prohibited actions"],
  "tool_philosophy": "1-2 sentences on tool usage preferences and patterns"
}}

**Available tools:**
{tools}

**System prompt to analyze:**
{raw_text}

CRITICAL: Return ONLY a single flat JSON object.
All 14 fields must be at the top level, not nested under
"operational" or "thematic" keys.
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


_NETWORK_MAX_RETRIES = 3
_NETWORK_BACKOFF_BASE = 2  # seconds: 1, 2, 4


def _llm_completion_with_retries(kwargs: dict) -> tuple:
    """Call litellm.completion with network retry logic.

    Returns (response, content_text). Raises AuthenticationError immediately,
    retries NetworkError up to _NETWORK_MAX_RETRIES times with exponential backoff.
    """
    last_err: Exception | None = None
    for attempt in range(_NETWORK_MAX_RETRIES):
        try:
            response = litellm.completion(**kwargs)
            return response, response.choices[0].message.content
        except Exception as e:
            classified = _classify_llm_error(e)
            if isinstance(classified, AuthenticationError):
                raise classified from e
            if isinstance(classified, NetworkError):
                last_err = classified
                if attempt < _NETWORK_MAX_RETRIES - 1:
                    delay = _NETWORK_BACKOFF_BASE**attempt
                    logger.warning(
                        "Network error (attempt %d/%d): %s", attempt + 1, _NETWORK_MAX_RETRIES, e
                    )
                    time.sleep(delay)
                    continue
                raise last_err from e
            raise  # Unknown error, don't retry
    raise last_err  # Should not reach here, but satisfy type checker


def analyze_assistant(
    raw_text: str,
    tool_names: list[str],
    assistant_name: str,
    model: str,
) -> tuple[AssistantAnalysis, dict[str, int]]:
    """Run LLM analysis on a single coding assistant's system prompt.

    Handles network retries (exponential backoff) and validation retries
    (one corrective prompt on parse failure).

    Returns:
        Tuple of (analysis, token_usage_dict).
    """
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
    logger.debug("Analyzing %s with %s...", assistant_name, model)
    response, content = _llm_completion_with_retries(kwargs)
    total_usage = total_usage + TokenUsage.from_response(response)

    try:
        return _parse_response(content), total_usage.to_dict()
    except Exception as first_error:
        error_msg = str(first_error)
        logger.warning("First parse failed for %s: validation error. Retrying...", assistant_name)
        logger.debug("Validation error details: %s", error_msg)

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

    response, content = _llm_completion_with_retries(kwargs)
    total_usage = total_usage + TokenUsage.from_response(response)

    return _parse_response(content), total_usage.to_dict()
