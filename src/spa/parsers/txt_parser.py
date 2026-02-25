"""Two-pass parser for txt/md prompts with mixed markdown headers and XML tags."""

import json
import re

from spa.parsers.base import ParsedPrompt, ParsedTools, PromptSection, ToolDefinition

# Match XML-style tags like <tool_description>, <critical_security_rules>, etc.
_XML_TAG_RE = re.compile(
    r"<(?P<tag>[a-zA-Z_][\w-]*)(?:\s[^>]*)?>(?P<content>.*?)</(?P=tag)>",
    re.DOTALL,
)

# Match markdown headings (# through ####)
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,4})\s+(?P<title>.+)$", re.MULTILINE)

# Match TypeScript-style tool definitions (Windsurf format)
_TS_TOOL_RE = re.compile(
    r"^(?://[^\n]*\n)*type\s+(?P<name>\w+)\s*=\s*\(_:\s*\{",
    re.MULTILINE,
)


def parse_prompt(text: str) -> ParsedPrompt:
    """Parse a text prompt using two passes: XML extraction then markdown splitting."""
    sections: list[PromptSection] = []
    has_xml = bool(_XML_TAG_RE.search(text))
    has_markdown = bool(_HEADING_RE.search(text))

    # Pass 1: extract top-level XML sections (deduplicate repeated tags)
    if has_xml:
        xml_seen: dict[str, PromptSection] = {}
        for m in _XML_TAG_RE.finditer(text):
            tag_name = m.group("tag")
            content = m.group("content").strip()
            if len(content) <= 50:
                continue
            if tag_name in xml_seen:
                # Merge repeated tags (e.g. multiple <example>) into one section
                xml_seen[tag_name].content += "\n---\n" + content
            else:
                section = PromptSection(
                    name=tag_name,
                    content=content,
                    level=1,
                    source="xml",
                )
                xml_seen[tag_name] = section
                sections.append(section)

    # Pass 2: split by markdown headings
    if has_markdown:
        headings = list(_HEADING_RE.finditer(text))
        for i, hm in enumerate(headings):
            level = len(hm.group("hashes"))
            title = hm.group("title").strip()
            start = hm.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[start:end].strip()
            if content:
                sections.append(PromptSection(
                    name=title,
                    content=content,
                    level=level,
                    source="markdown",
                ))

    # Determine format type
    if has_xml and has_markdown:
        fmt = "mixed"
    elif has_xml:
        fmt = "xml"
    elif has_markdown:
        fmt = "markdown"
    else:
        fmt = "plain"

    return ParsedPrompt(raw_text=text, sections=sections, format_type=fmt)


def parse_tools_txt(text: str) -> ParsedTools:
    """Parse Windsurf-style TypeScript tool definitions from text."""
    tools: list[ToolDefinition] = []
    # Split by 'type <name> = ' declarations
    parts = re.split(r"(?=^(?://[^\n]*\n)*type\s+\w+\s*=)", text, flags=re.MULTILINE)

    for part in parts:
        m = _TS_TOOL_RE.match(part)
        if not m:
            continue
        name = m.group("name")
        # Extract the leading comment as description
        comment_lines = []
        for line in part.splitlines():
            if line.startswith("//"):
                comment_lines.append(line.lstrip("/ "))
            else:
                break
        description = " ".join(comment_lines) if comment_lines else ""
        tools.append(ToolDefinition(name=name, description=description))

    return ParsedTools(tools=tools, source_format="txt")


# Claude Code style: ## ToolName heading followed later by --- separator
_CC_HEADING_RE = re.compile(r"^##\s+(?P<name>[A-Za-z]\w*)\s*$", re.MULTILINE)
_CC_SEP_RE = re.compile(r"^---\s*$", re.MULTILINE)


def _bracket_match(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Find matching closing bracket. Returns end index (exclusive) or -1."""
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
    return -1


def _extract_claude_code_tools(text: str) -> list[ToolDefinition]:
    """Extract tools in Claude Code style: ## Name, description, {JSON schema}, ---."""
    tools: list[ToolDefinition] = []
    for hm in _CC_HEADING_RE.finditer(text):
        name = hm.group("name")
        section_start = hm.end()
        # Find the next --- separator after this heading
        sep = _CC_SEP_RE.search(text, section_start)
        if not sep:
            continue
        section = text[section_start:sep.start()]
        # Find the last top-level JSON object in this section (the schema).
        # Scan forward, bracket-match each '{', keep the last valid parse.
        params: dict = {}
        schema_start = -1
        k = 0
        while k < len(section):
            brace_pos = section.find("{", k)
            if brace_pos == -1:
                break
            end = _bracket_match(section, brace_pos, "{", "}")
            if end == -1:
                k = brace_pos + 1
                continue
            candidate = section[brace_pos:end]
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                k = brace_pos + 1
                continue
            if isinstance(parsed, dict):
                params = parsed
                schema_start = brace_pos
            k = end
        if schema_start == -1:
            continue
        desc = section[:schema_start].strip()
        tools.append(ToolDefinition(
            name=name, description=desc, parameters=params, source="inline",
        ))
    return tools


def _parse_tool_object(obj: dict) -> ToolDefinition | None:
    """Parse a single tool dict, handling OpenAI-wrapped format."""
    if "function" in obj and isinstance(obj["function"], dict):
        obj = obj["function"]
    name = obj.get("name")
    if not name:
        return None
    return ToolDefinition(
        name=name,
        description=obj.get("description", ""),
        parameters=obj.get("parameters", {}),
        source="inline",
    )


def _extract_openai_function_tools(text: str) -> list[ToolDefinition]:
    """Extract tools from JSON arrays or concatenated JSON objects in text.

    Handles:
    - JSON arrays: [{"name":...}, ...] or [{"type":"function","function":{...}}, ...]
    - Concatenated objects: {"type":"function","function":{...}},{"type":"function",...}
    """
    tools: list[ToolDefinition] = []
    i = 0
    while i < len(text):
        # Find next [ or { that could start a tool definition
        next_bracket = text.find("[", i)
        next_brace = text.find("{", i)
        if next_bracket == -1 and next_brace == -1:
            break

        # Try array first if it comes before a brace
        if next_bracket != -1 and (next_brace == -1 or next_bracket <= next_brace):
            peek = text[next_bracket:next_bracket + 200]
            if '"name"' in peek and '"description"' in peek:
                end = _bracket_match(text, next_bracket, "[", "]")
                if end != -1:
                    candidate = text[next_bracket:end]
                    try:
                        arr = json.loads(candidate)
                    except json.JSONDecodeError:
                        pass
                    else:
                        if isinstance(arr, list):
                            for item in arr:
                                if isinstance(item, dict):
                                    tool = _parse_tool_object(item)
                                    if tool:
                                        tools.append(tool)
                            i = end
                            continue
            i = next_bracket + 1
            continue

        # Try individual object (Cursor concatenated format)
        peek = text[next_brace:next_brace + 200]
        if '"name"' in peek and '"description"' in peek:
            end = _bracket_match(text, next_brace, "{", "}")
            if end != -1:
                candidate = text[next_brace:end]
                try:
                    obj = json.loads(candidate)
                except json.JSONDecodeError:
                    i = next_brace + 1
                    continue
                if isinstance(obj, dict):
                    tool = _parse_tool_object(obj)
                    if tool:
                        tools.append(tool)
                i = end
                continue
        i = next_brace + 1
    return tools


def extract_inline_tools(text: str) -> list[ToolDefinition]:
    """Extract all inline tool definitions from prompt text.

    Handles three formats:
    1. Claude Code style (## Name + JSON schema + ---)
    2. OpenAI-style JSON arrays ([{"name":...}, ...])
    3. TypeScript declarations (via parse_tools_txt)
    """
    seen: set[str] = set()
    tools: list[ToolDefinition] = []

    for extractor in (_extract_claude_code_tools, _extract_openai_function_tools):
        for tool in extractor(text):
            if tool.name not in seen:
                seen.add(tool.name)
                tools.append(tool)

    # Format 3: TypeScript declarations (already handled by parse_tools_txt)
    for tool in parse_tools_txt(text).tools:
        if tool.name not in seen:
            seen.add(tool.name)
            tools.append(ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
                source="inline",
            ))

    return tools
