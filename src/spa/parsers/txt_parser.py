"""Two-pass parser for txt/md prompts with mixed markdown headers and XML tags."""

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

    # Pass 1: extract top-level XML sections
    if has_xml:
        for m in _XML_TAG_RE.finditer(text):
            tag_name = m.group("tag")
            # Skip small inline tags (like <example> used as formatting)
            content = m.group("content").strip()
            if len(content) > 50:
                sections.append(PromptSection(
                    name=tag_name,
                    content=content,
                    level=1,
                    source="xml",
                ))

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
