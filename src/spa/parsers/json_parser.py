"""Parser for JSON tool definition files."""

import json

from spa.parsers.base import ParsedTools, ToolDefinition


def parse_tools_json(text: str) -> ParsedTools:
    """Parse tool definitions from JSON.

    Handles formats:
    - {"tools": [{"name": ..., "description": ..., "input_schema": ...}]}
    - [{"name": ..., "description": ..., ...}]  (bare array)
    """
    data = json.loads(text)

    if isinstance(data, dict):
        tool_list = data.get("tools", [])
    elif isinstance(data, list):
        tool_list = data
    else:
        return ParsedTools()

    tools: list[ToolDefinition] = []
    for item in tool_list:
        if not isinstance(item, dict):
            continue
        name = item.get("name", item.get("function", {}).get("name", ""))
        if not name:
            continue
        desc = item.get("description", item.get("function", {}).get("description", ""))
        params = item.get("input_schema", item.get("parameters", {}))
        tools.append(ToolDefinition(name=name, description=desc, parameters=params))

    return ParsedTools(tools=tools, source_format="json")
