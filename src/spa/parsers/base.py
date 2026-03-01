"""Base dataclasses for parsed prompts and tools."""

from dataclasses import dataclass, field
from enum import StrEnum


class FormatType(StrEnum):
    """Format of a parsed prompt file."""

    MARKDOWN = "markdown"
    XML = "xml"
    MIXED = "mixed"
    YAML = "yaml"
    PLAIN = "plain"
    UNKNOWN = "unknown"


@dataclass
class PromptSection:
    """A named section within a prompt."""

    name: str
    content: str
    level: int = 1  # heading level or nesting depth
    source: str = "markdown"  # "markdown" or "xml"


@dataclass
class ParsedPrompt:
    """Result of parsing a single prompt file."""

    raw_text: str
    sections: list[PromptSection] = field(default_factory=list)
    format_type: FormatType = FormatType.UNKNOWN


@dataclass
class ToolDefinition:
    """A single tool extracted from a tools file."""

    name: str
    description: str = ""
    parameters: dict = field(default_factory=dict)
    source: str = "file"  # "file" or "inline"


@dataclass
class ParsedTools:
    """Result of parsing a tools file."""

    tools: list[ToolDefinition] = field(default_factory=list)
    source_format: str = "json"  # "json" or "txt"
