"""LLM-powered thematic analysis of coding assistant system prompts."""

import json
import logging
import os

from spa.llm.schemas import AgentAnalysis

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are analyzing the system prompt of an AI coding assistant called "{agent_name}".

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


def _build_prompt(raw_text: str, tool_names: list[str], agent_name: str) -> str:
    """Build the analysis prompt from template."""
    if tool_names:
        tool_list = "\n".join(f"- {name}" for name in tool_names)
    else:
        tool_list = "No tools defined."
    return PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        raw_text=raw_text,
        tool_list=tool_list,
    )


def _parse_response(content: str) -> AgentAnalysis:
    """Parse LLM response text into AgentAnalysis, stripping markdown fences if present."""
    text = content.strip()
    if text.startswith("```"):
        # Strip ```json ... ``` fences
        lines = text.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return AgentAnalysis.model_validate_json(text)


def analyze_agent(
    raw_text: str,
    tool_names: list[str],
    agent_name: str,
    model: str,
) -> AgentAnalysis:
    """Run LLM analysis on a single coding assistant's system prompt.

    Retries once on validation failure with a corrective prompt.
    """
    import litellm

    api_key = os.environ.get("LLM_API_KEY")
    base_url = os.environ.get("LLM_BASE_URL")

    prompt = _build_prompt(raw_text, tool_names, agent_name)

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

    # First attempt
    logger.info("Analyzing %s with %s...", agent_name, model)
    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content

    try:
        return _parse_response(content)
    except Exception as first_error:
        error_msg = str(first_error)
        logger.warning("First parse failed for %s: %s. Retrying...", agent_name, error_msg)

    # Retry with corrective prompt
    kwargs["messages"].append({"role": "assistant", "content": content})
    kwargs["messages"].append({
        "role": "user",
        "content": (
            f"Your response failed validation: {error_msg}\n"
            "Please fix the JSON and return ONLY valid JSON matching the schema."
        ),
    })

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    return _parse_response(content)
