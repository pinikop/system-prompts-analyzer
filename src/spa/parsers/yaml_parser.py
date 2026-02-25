"""Parser for Amp-style YAML prompt files."""

import yaml

from spa.parsers.base import ParsedPrompt
from spa.parsers.txt_parser import parse_prompt as parse_txt


def parse_yaml_prompt(text: str) -> ParsedPrompt:
    """Extract prompt text from YAML structure and parse it as text.

    Amp YAML has structure like:
        system:
          - type: text
            text: >
              <the actual prompt>
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        # Malformed YAML (undefined aliases, etc.) - fall back to text parsing
        result = parse_txt(text)
        result.format_type = "yaml"
        return result
    if not isinstance(data, dict):
        return ParsedPrompt(raw_text=text, format_type="yaml")

    # Extract text from system messages
    prompt_parts: list[str] = []
    system = data.get("system", [])
    if isinstance(system, list):
        for item in system:
            if isinstance(item, dict) and item.get("type") == "text":
                prompt_parts.append(item.get("text", ""))
    elif isinstance(system, str):
        prompt_parts.append(system)

    if not prompt_parts:
        # Fallback: try to get any string values
        for v in data.values():
            if isinstance(v, str) and len(v) > 100:
                prompt_parts.append(v)

    extracted = "\n\n".join(prompt_parts)
    if not extracted:
        return ParsedPrompt(raw_text=text, format_type="yaml")

    result = parse_txt(extracted)
    result.format_type = "yaml"
    return result
