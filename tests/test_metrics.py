"""Tests for metrics computation."""

from pathlib import Path

from spa.metrics.rule_based import compute_metrics
from spa.parsers.base import ParsedPrompt, PromptSection

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class TestRuleBasedMetrics:
    def test_word_count(self):
        prompt = ParsedPrompt(raw_text="hello world foo bar baz")
        m = compute_metrics(prompt)
        assert m["word_count"] == 5

    def test_line_count(self):
        prompt = ParsedPrompt(raw_text="line1\nline2\nline3\n")
        m = compute_metrics(prompt)
        assert m["line_count"] == 3

    def test_char_count(self):
        prompt = ParsedPrompt(raw_text="abc")
        m = compute_metrics(prompt)
        assert m["char_count"] == 3

    def test_section_count(self):
        prompt = ParsedPrompt(
            raw_text="text",
            sections=[
                PromptSection(name="A", content="..."),
                PromptSection(name="B", content="..."),
            ],
        )
        m = compute_metrics(prompt)
        assert m["section_count"] == 2

    def test_directive_keywords(self):
        prompt = ParsedPrompt(raw_text="You MUST do X. NEVER do Y. You MUST also Z.")
        m = compute_metrics(prompt)
        assert m["directive_keywords"]["MUST"] == 2
        assert m["directive_keywords"]["NEVER"] == 1
        assert m["directive_count"] == 3

    def test_directive_density(self):
        prompt = ParsedPrompt(raw_text="You MUST do this thing. NEVER do that thing here.")
        m = compute_metrics(prompt)
        assert m["directive_density"] > 0

    def test_example_count(self):
        prompt = ParsedPrompt(
            raw_text="<example>\nfoo\n</example>\n<example>\nbar\n</example>"
        )
        m = compute_metrics(prompt)
        assert m["example_count"] == 2

    def test_format_type(self):
        prompt = ParsedPrompt(raw_text="text", format_type="mixed")
        m = compute_metrics(prompt)
        assert m["format_type"] == "mixed"

    def test_real_prompt(self):
        path = DATA_DIR / "Anthropic" / "Claude Code" / "Prompt.txt"
        if not path.exists():
            return
        from spa.parsers.txt_parser import parse_prompt
        parsed = parse_prompt(path.read_text())
        m = compute_metrics(parsed)
        assert m["word_count"] > 1000
        assert m["directive_count"] > 0
        assert m["section_count"] > 5


from spa.metrics.tool_metrics import compute_tool_metrics
from spa.parsers.base import ToolDefinition


class TestToolMetrics:
    def test_basic_counts(self):
        tools = [
            ToolDefinition(name="Bash", description="Run commands", source="inline"),
            ToolDefinition(name="Read", description="Read files", source="inline"),
            ToolDefinition(name="Write", description="Write files", source="file"),
        ]
        m = compute_tool_metrics(tools)
        assert m["count"] == 3
        assert m["names"] == ["Bash", "Read", "Write"]
        assert m["sources"]["inline"] == 2
        assert m["sources"]["file"] == 1

    def test_category_classification(self):
        tools = [
            ToolDefinition(name="Bash", description="Execute shell commands"),
            ToolDefinition(name="Read", description="Read file contents"),
            ToolDefinition(name="GitCommit", description="Commit changes to git"),
        ]
        m = compute_tool_metrics(tools)
        assert "execution" in m["categories"]
        assert "Bash" in m["categories"]["execution"]

    def test_empty_tools(self):
        m = compute_tool_metrics([])
        assert m["count"] == 0
        assert m["names"] == []
