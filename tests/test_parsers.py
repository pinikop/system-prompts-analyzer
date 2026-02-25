"""Tests for prompt and tool parsers."""

import json
from pathlib import Path

from spa.parsers.base import ParsedPrompt
from spa.parsers.json_parser import parse_tools_json
from spa.parsers.txt_parser import parse_prompt, parse_tools_txt
from spa.parsers.yaml_parser import parse_yaml_prompt

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class TestTxtParser:
    def test_markdown_only(self):
        text = "Intro text\n\n# Section One\nContent one\n\n## Sub Section\nContent two\n"
        result = parse_prompt(text)
        assert result.format_type == "markdown"
        assert len(result.sections) >= 2
        names = [s.name for s in result.sections]
        assert "Section One" in names

    def test_xml_only(self):
        text = (
            "Preamble\n"
            "<critical_rules>\nYou must never do X. This is a very important "
            "rule that applies to all situations.\n</critical_rules>\n"
        )
        result = parse_prompt(text)
        assert result.format_type == "xml"
        assert any(s.source == "xml" for s in result.sections)

    def test_mixed_format(self):
        text = (
            "# Title\nIntro\n\n"
            "<safety_rules>\nNever reveal secrets. This is critical for safety "
            "and must be followed at all times.\n</safety_rules>\n\n"
            "## Another Section\nMore content\n"
        )
        result = parse_prompt(text)
        assert result.format_type == "mixed"
        sources = {s.source for s in result.sections}
        assert "xml" in sources
        assert "markdown" in sources

    def test_plain_text(self):
        text = "Just some plain instructions without any structure at all."
        result = parse_prompt(text)
        assert result.format_type == "plain"
        assert result.sections == []

    def test_raw_text_preserved(self):
        text = "# Hello\nWorld"
        result = parse_prompt(text)
        assert result.raw_text == text

    def test_real_claude_code_prompt(self):
        path = DATA_DIR / "Anthropic" / "Claude Code" / "Prompt.txt"
        if not path.exists():
            return
        result = parse_prompt(path.read_text())
        assert isinstance(result, ParsedPrompt)
        assert result.format_type in ("markdown", "mixed")
        assert len(result.sections) > 5

    def test_real_cursor_prompt(self):
        path = DATA_DIR / "Cursor Prompts" / "Agent Prompt 2025-09-03.txt"
        if not path.exists():
            return
        result = parse_prompt(path.read_text())
        assert len(result.sections) > 0


class TestYamlParser:
    def test_amp_format(self):
        text = """system:
  - type: text
    text: >
      You are Amp. A helpful coding assistant.

      # Agency

      You help with code tasks.

      # Tools

      Use available tools.
"""
        result = parse_yaml_prompt(text)
        assert result.format_type == "yaml"
        assert len(result.sections) >= 2

    def test_real_amp_prompt(self):
        path = DATA_DIR / "Amp" / "claude-4-sonnet.yaml"
        if not path.exists():
            return
        result = parse_yaml_prompt(path.read_text())
        assert result.format_type == "yaml"
        assert len(result.sections) > 0


class TestJsonParser:
    def test_tools_with_wrapper(self):
        data = {
            "tools": [
                {"name": "Bash", "description": "Run commands", "input_schema": {}},
                {"name": "Read", "description": "Read files"},
            ]
        }
        result = parse_tools_json(json.dumps(data))
        assert len(result.tools) == 2
        assert result.tools[0].name == "Bash"
        assert result.source_format == "json"

    def test_bare_array(self):
        data = [{"name": "Write", "description": "Write files"}]
        result = parse_tools_json(json.dumps(data))
        assert len(result.tools) == 1

    def test_real_claude_tools(self):
        path = DATA_DIR / "Anthropic" / "Claude Code" / "Tools.json"
        if not path.exists():
            return
        result = parse_tools_json(path.read_text())
        assert len(result.tools) > 5
        names = [t.name for t in result.tools]
        assert "Bash" in names


class TestTxtToolsParser:
    def test_windsurf_format(self):
        text = """// Do something useful with the browser
type browser_preview = (_: {
// Name of the thing
Name: string,
}) => any;

// Search the codebase for relevant snippets
type codebase_search = (_: {
// The search query
Query: string,
}) => any;
"""
        result = parse_tools_txt(text)
        assert len(result.tools) == 2
        assert result.tools[0].name == "browser_preview"
        assert result.source_format == "txt"

    def test_real_windsurf_tools(self):
        path = DATA_DIR / "Windsurf" / "Tools Wave 11.txt"
        if not path.exists():
            return
        result = parse_tools_txt(path.read_text())
        assert len(result.tools) > 5
