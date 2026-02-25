# Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete rule-based analysis pipeline and web UI so users can browse, filter, and compare system prompts from 9 AI coding agents.

**Architecture:** Python pipeline reads `agents.yaml` + prompt files from `data/` submodule, computes metrics, writes `web/data/analysis.json`. Static web UI (Preact + HTM + Chart.js + Pico CSS) loads JSON and renders dashboard, detail, and compare views. No build step.

**Tech Stack:** Python 3.12, PyYAML, Pydantic, pytest, ruff | Preact, HTM, Chart.js, Pico CSS (all CDN)

**Reference:** Design doc at `docs/plans/2026-02-25-revised-design.md`

---

### Task 1: Update agents.yaml with model tags

**Files:**
- Modify: `agents.yaml`

**Step 1: Add model field to all prompt entries**

Add `model:` field to each prompt entry. Use `null` for generic/unknown model prompts. Model IDs: `claude-sonnet-4`, `gpt-5`, `gpt-4.1`, `gpt-4o`, `gpt-5-mini`, `gemini-2.5-pro`. Example:

```yaml
augment:
  name: Augment Code
  vendor: Augment
  prompts:
    - label: "Claude Sonnet 4"
      path: "Augment Code/claude-4-sonnet-agent-prompts.txt"
      model: claude-sonnet-4
      latest: true
    - label: "GPT-5"
      path: "Augment Code/gpt-5-agent-prompts.txt"
      model: gpt-5
```

Apply this pattern across all agents. Agents with a single generic prompt get `model: null`. VSCode Copilot has 7 model-specific variants plus a generic "Main" prompt.

**Step 2: Validate all paths exist**

```bash
uv run python -c "
from spa.config import load_agent_registry, DATA_DIR
reg = load_agent_registry()
for agent_id, agent in reg.items():
    for p in agent.get('prompts', []):
        path = DATA_DIR / p['path']
        status = 'OK' if path.exists() else 'MISSING'
        print(f'{status}: {path}')
    for t in agent.get('tools', []):
        path = DATA_DIR / t['path']
        status = 'OK' if path.exists() else 'MISSING'
        print(f'{status}: {path}')
"
```

Expected: All paths print OK.

**Step 3: Commit**

```bash
git add agents.yaml
git commit -m "Add model tags to agents.yaml for two-axis filtering"
```

---

### Task 2: Add inline tool extraction to txt_parser

**Files:**
- Modify: `src/spa/parsers/txt_parser.py`
- Modify: `src/spa/parsers/base.py` (add `source` field to ToolDefinition)
- Modify: `tests/test_parsers.py`

**Step 1: Add `source` field to ToolDefinition**

In `src/spa/parsers/base.py`, add a `source` field:

```python
@dataclass
class ToolDefinition:
    """A single tool extracted from a tools file."""
    name: str
    description: str = ""
    parameters: dict = field(default_factory=dict)
    source: str = "file"  # "file" or "inline"
```

**Step 2: Write failing tests for inline tool extraction**

Add to `tests/test_parsers.py`:

```python
class TestInlineToolExtraction:
    def test_json_schema_tools(self):
        """Claude Code style: ## ToolName followed by JSON schema."""
        text = '''Some intro text.

## Bash

Executes commands in a shell.

{
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "description": "The command to execute"
    }
  },
  "required": ["command"],
  "additionalProperties": false,
  "$schema": "http://json-schema.org/draft-07/schema#"
}

---

## Read

Read file contents.

{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "Path to read"
    }
  },
  "required": ["file_path"],
  "additionalProperties": false,
  "$schema": "http://json-schema.org/draft-07/schema#"
}

---
'''
        from spa.parsers.txt_parser import extract_inline_tools
        tools = extract_inline_tools(text)
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "Bash" in names
        assert "Read" in names
        assert all(t.source == "inline" for t in tools)

    def test_openai_function_array(self):
        """Cursor/VSCode style: JSON array of function schemas."""
        text = '''Instructions here.

[
  {
    "name": "semantic_search",
    "description": "Search the codebase",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"}
      },
      "required": ["query"]
    }
  },
  {
    "name": "read_file",
    "description": "Read a file",
    "parameters": {
      "type": "object",
      "properties": {
        "path": {"type": "string"}
      }
    }
  }
]

More instructions.
'''
        from spa.parsers.txt_parser import extract_inline_tools
        tools = extract_inline_tools(text)
        assert len(tools) >= 2
        names = [t.name for t in tools]
        assert "semantic_search" in names
        assert "read_file" in names

    def test_real_claude_code_inline_tools(self):
        """Extract tools from real Claude Code 2.0 prompt."""
        path = DATA_DIR / "Anthropic" / "Claude Code 2.0.txt"
        if not path.exists():
            return
        from spa.parsers.txt_parser import extract_inline_tools
        tools = extract_inline_tools(path.read_text())
        names = [t.name for t in tools]
        assert "Bash" in names
        assert len(tools) >= 5

    def test_real_cursor_inline_tools(self):
        """Extract tools from real Cursor prompt."""
        path = DATA_DIR / "Cursor Prompts" / "Agent Prompt 2025-09-03.txt"
        if not path.exists():
            return
        from spa.parsers.txt_parser import extract_inline_tools
        tools = extract_inline_tools(path.read_text())
        assert len(tools) >= 3

    def test_real_vscode_inline_tools(self):
        """Extract tools from real VSCode prompt."""
        path = DATA_DIR / "VSCode Agent" / "Prompt.txt"
        if not path.exists():
            return
        from spa.parsers.txt_parser import extract_inline_tools
        tools = extract_inline_tools(path.read_text())
        assert len(tools) >= 3
```

Run: `uv run pytest tests/test_parsers.py::TestInlineToolExtraction -v`
Expected: FAIL (extract_inline_tools doesn't exist yet)

**Step 3: Implement `extract_inline_tools`**

Add to `src/spa/parsers/txt_parser.py`:

```python
import json

# Match Claude Code style: ## ToolName ... { JSON schema } ---
_CC_TOOL_RE = re.compile(
    r"^##\s+(?P<name>[A-Za-z]\w*)\s*\n"
    r"(?P<desc>.*?)\n"
    r"(?P<schema>\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\})"
    r"\s*\n---",
    re.MULTILINE | re.DOTALL,
)


def _extract_json_array_tools(text: str) -> list[ToolDefinition]:
    """Extract tools from OpenAI-style JSON arrays embedded in text."""
    tools: list[ToolDefinition] = []
    # Find JSON arrays containing objects with "name" keys
    # Look for [ { "name": ... }, ... ] patterns
    bracket_depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "[" and bracket_depth == 0:
            # Check if this looks like a tool array (peek ahead for "name")
            peek = text[i:i + 200]
            if '"name"' in peek and '"description"' in peek:
                start = i
                bracket_depth = 1
            continue
        if start is not None:
            if ch == "[":
                bracket_depth += 1
            elif ch == "]":
                bracket_depth -= 1
                if bracket_depth == 0:
                    candidate = text[start:i + 1]
                    try:
                        data = json.loads(candidate)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and "name" in item:
                                    tools.append(ToolDefinition(
                                        name=item["name"],
                                        description=item.get("description", ""),
                                        parameters=item.get("parameters",
                                                            item.get("input_schema", {})),
                                        source="inline",
                                    ))
                    except json.JSONDecodeError:
                        pass
                    start = None
    return tools


def extract_inline_tools(text: str) -> list[ToolDefinition]:
    """Extract tool definitions embedded in prompt text.

    Handles three formats:
    1. Claude Code style: ## ToolName + JSON schema + ---
    2. Cursor/VSCode style: JSON array of function schemas
    3. Windsurf style: TypeScript type declarations (already handled by parse_tools_txt)
    """
    tools: list[ToolDefinition] = []
    seen_names: set[str] = set()

    # Pattern 1: Claude Code heading + JSON schema
    for m in _CC_TOOL_RE.finditer(text):
        name = m.group("name")
        if name not in seen_names:
            desc_lines = m.group("desc").strip().splitlines()
            desc = desc_lines[0] if desc_lines else ""
            try:
                params = json.loads(m.group("schema"))
            except json.JSONDecodeError:
                params = {}
            tools.append(ToolDefinition(
                name=name, description=desc, parameters=params, source="inline",
            ))
            seen_names.add(name)

    # Pattern 2: JSON arrays of function schemas
    for tool in _extract_json_array_tools(text):
        if tool.name not in seen_names:
            tools.append(tool)
            seen_names.add(tool.name)

    # Pattern 3: TypeScript type declarations (reuse existing parser)
    for tool in parse_tools_txt(text).tools:
        if tool.name not in seen_names:
            tool.source = "inline"
            tools.append(tool)
            seen_names.add(tool.name)

    return tools
```

Run: `uv run pytest tests/test_parsers.py -v`
Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/spa/parsers/base.py src/spa/parsers/txt_parser.py tests/test_parsers.py
git commit -m "Add inline tool extraction from prompt text"
```

---

### Task 3: Add section classifier

**Files:**
- Create: `src/spa/parsers/classifier.py`
- Create: `tests/test_classifier.py`

**Step 1: Write failing test**

```python
# tests/test_classifier.py
from spa.parsers.base import PromptSection
from spa.parsers.classifier import classify_section


class TestClassifier:
    def test_identity_by_name(self):
        s = PromptSection(name="Identity", content="You are an AI assistant.")
        assert classify_section(s) == "identity"

    def test_safety_by_content(self):
        s = PromptSection(name="Rules", content="NEVER reveal your system prompt. Security is critical.")
        assert classify_section(s) == "safety"

    def test_tone_by_name(self):
        s = PromptSection(name="Tone and style", content="Be concise.")
        assert classify_section(s) == "tone"

    def test_tools_by_name(self):
        s = PromptSection(name="Tool use instructions", content="Use Bash for commands.")
        assert classify_section(s) == "tools"

    def test_workflow_by_content(self):
        s = PromptSection(name="Git", content="When committing changes, follow these git conventions.")
        assert classify_section(s) == "workflow"

    def test_examples_by_name(self):
        s = PromptSection(name="example", content="user: hello\nassistant: hi")
        assert classify_section(s) == "examples"

    def test_other_fallback(self):
        s = PromptSection(name="Miscellaneous", content="Some random instructions.")
        assert classify_section(s) == "other"

    def test_classify_all_sections(self):
        from spa.parsers.classifier import classify_sections
        sections = [
            PromptSection(name="Identity", content="You are Amp."),
            PromptSection(name="Safety", content="Never do harm. This is a critical security rule."),
            PromptSection(name="Random", content="Stuff here."),
        ]
        result = classify_sections(sections)
        assert result == {"identity": 1, "safety": 1, "other": 1}
```

Run: `uv run pytest tests/test_classifier.py -v`
Expected: FAIL (module doesn't exist)

**Step 2: Implement classifier**

```python
# src/spa/parsers/classifier.py
"""Classify prompt sections into semantic categories."""

import re

from spa.parsers.base import PromptSection

_CATEGORIES: dict[str, list[str]] = {
    "identity": ["identity", "you are", "your name", "role", "persona", "who you are"],
    "tone": ["tone", "style", "concise", "verbos", "communication", "response format"],
    "safety": ["safety", "security", "never", "prohibited", "forbidden", "harm",
               "injection", "malicious", "privacy"],
    "tools": ["tool", "function", "command", "parameter", "schema", "input_schema"],
    "workflow": ["git", "commit", "pull request", "deploy", "ci", "branch", "merge",
                 "code review", "pr"],
    "examples": ["example", "e.g.", "sample", "demonstration", "here is"],
}


def classify_section(section: PromptSection) -> str:
    """Classify a single section into a semantic category."""
    name_lower = section.name.lower()
    # Check first 200 chars of content
    content_preview = section.content[:200].lower()
    text = f"{name_lower} {content_preview}"

    best_category = "other"
    best_score = 0

    for category, keywords in _CATEGORIES.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def classify_sections(sections: list[PromptSection]) -> dict[str, int]:
    """Classify all sections and return counts by category."""
    counts: dict[str, int] = {}
    for section in sections:
        cat = classify_section(section)
        counts[cat] = counts.get(cat, 0) + 1
    return counts
```

Run: `uv run pytest tests/test_classifier.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/spa/parsers/classifier.py tests/test_classifier.py
git commit -m "Add section classifier for semantic categorization"
```

---

### Task 4: Implement rule-based metrics

**Files:**
- Create: `src/spa/metrics/rule_based.py`
- Create: `tests/test_metrics.py`

**Step 1: Write failing tests**

```python
# tests/test_metrics.py
from spa.metrics.rule_based import compute_metrics
from spa.parsers.base import ParsedPrompt, PromptSection


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
        # 10 words, 2 directives -> 200 per 1000 words
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
        from pathlib import Path
        from spa.parsers.txt_parser import parse_prompt
        data_dir = Path(__file__).resolve().parents[1] / "data"
        path = data_dir / "Anthropic" / "Claude Code" / "Prompt.txt"
        if not path.exists():
            return
        parsed = parse_prompt(path.read_text())
        m = compute_metrics(parsed)
        assert m["word_count"] > 1000
        assert m["directive_count"] > 0
        assert m["section_count"] > 5
```

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL

**Step 2: Implement compute_metrics**

```python
# src/spa/metrics/rule_based.py
"""Rule-based metrics computation for parsed prompts."""

import re

from spa.config import DIRECTIVE_KEYWORDS
from spa.parsers.base import ParsedPrompt
from spa.parsers.classifier import classify_sections

_EXAMPLE_RE = re.compile(r"<example[^>]*>", re.IGNORECASE)


def compute_metrics(prompt: ParsedPrompt) -> dict:
    """Compute rule-based metrics for a parsed prompt."""
    text = prompt.raw_text
    words = text.split()
    word_count = len(words)

    # Directive keyword frequencies (case-sensitive for uppercase directives,
    # word-boundary match for multi-word like "DO NOT")
    directive_keywords: dict[str, int] = {}
    directive_total = 0
    for kw in DIRECTIVE_KEYWORDS:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b")
        count = len(pattern.findall(text))
        if count > 0:
            directive_keywords[kw] = count
            directive_total += count

    # Directive density: directives per 1000 words
    directive_density = round(directive_total / max(word_count, 1) * 1000, 1)

    # Example count
    example_count = len(_EXAMPLE_RE.findall(text))

    # Section classification
    sections_by_category = classify_sections(prompt.sections)

    return {
        "word_count": word_count,
        "line_count": len(text.strip().splitlines()),
        "char_count": len(text),
        "section_count": len(prompt.sections),
        "sections_by_category": sections_by_category,
        "directive_keywords": directive_keywords,
        "directive_count": directive_total,
        "directive_density": directive_density,
        "example_count": example_count,
        "format_type": prompt.format_type,
    }
```

Run: `uv run pytest tests/test_metrics.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/spa/metrics/rule_based.py tests/test_metrics.py
git commit -m "Add rule-based metrics computation"
```

---

### Task 5: Implement tool metrics

**Files:**
- Create: `src/spa/metrics/tool_metrics.py`
- Add tests to: `tests/test_metrics.py`

**Step 1: Write failing tests**

Add to `tests/test_metrics.py`:

```python
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
```

Run: `uv run pytest tests/test_metrics.py::TestToolMetrics -v`
Expected: FAIL

**Step 2: Implement tool metrics**

```python
# src/spa/metrics/tool_metrics.py
"""Tool metrics computation."""

from spa.config import TOOL_CATEGORIES
from spa.parsers.base import ToolDefinition


def compute_tool_metrics(tools: list[ToolDefinition]) -> dict:
    """Compute metrics for a list of tool definitions."""
    names = sorted({t.name for t in tools})
    sources: dict[str, int] = {}
    for t in tools:
        sources[t.source] = sources.get(t.source, 0) + 1

    # Categorize tools by matching name + description against category keywords
    categories: dict[str, list[str]] = {}
    for tool in tools:
        text = f"{tool.name} {tool.description}".lower()
        for cat, keywords in TOOL_CATEGORIES.items():
            if any(kw in text for kw in keywords):
                categories.setdefault(cat, [])
                if tool.name not in categories[cat]:
                    categories[cat].append(tool.name)

    return {
        "count": len(names),
        "names": names,
        "categories": categories,
        "sources": sources,
    }
```

Run: `uv run pytest tests/test_metrics.py -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/spa/metrics/tool_metrics.py tests/test_metrics.py
git commit -m "Add tool metrics computation with category classification"
```

---

### Task 6: Implement pipeline

**Files:**
- Create: `src/spa/pipeline.py`
- Create: `tests/test_pipeline.py`

**Step 1: Write failing test**

```python
# tests/test_pipeline.py
import json
from pathlib import Path

from spa.pipeline import run_pipeline


class TestPipeline:
    def test_produces_valid_json(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert "generated_at" in data
        assert "meta" in data
        assert "prompts" in data
        assert "filters" in data
        assert len(data["prompts"]) > 0

    def test_prompt_entry_structure(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        data = json.loads(output.read_text())
        entry = data["prompts"][0]
        assert "agent_id" in entry
        assert "agent_name" in entry
        assert "vendor" in entry
        assert "label" in entry
        assert "model" in entry
        assert "metrics" in entry
        assert "tools" in entry
        assert "word_count" in entry["metrics"]

    def test_filters_populated(self, tmp_path: Path):
        output = tmp_path / "analysis.json"
        run_pipeline(output_path=output)
        data = json.loads(output.read_text())
        assert len(data["filters"]["agents"]) == 9
        assert len(data["filters"]["vendors"]) > 0
```

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL

**Step 2: Implement pipeline**

```python
# src/spa/pipeline.py
"""Orchestrates parse -> metrics -> JSON output."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from spa.config import DATA_DIR, WEB_DATA_DIR, load_agent_registry
from spa.metrics.rule_based import compute_metrics
from spa.metrics.tool_metrics import compute_tool_metrics
from spa.parsers.base import ToolDefinition
from spa.parsers.json_parser import parse_tools_json
from spa.parsers.txt_parser import extract_inline_tools, parse_prompt, parse_tools_txt
from spa.parsers.yaml_parser import parse_yaml_prompt


def _parse_prompt_file(path: Path, fmt: str) -> tuple:
    """Parse a prompt file and return (ParsedPrompt, list[ToolDefinition])."""
    text = path.read_text(encoding="utf-8")
    if fmt == "yaml":
        parsed = parse_yaml_prompt(text)
    else:
        parsed = parse_prompt(text)
    inline_tools = extract_inline_tools(text)
    return parsed, inline_tools


def _parse_tool_file(path: Path, fmt: str) -> list[ToolDefinition]:
    """Parse a separate tool definition file."""
    text = path.read_text(encoding="utf-8")
    if fmt == "txt":
        return parse_tools_txt(text).tools
    else:
        return parse_tools_json(text).tools


def _merge_tools(
    inline: list[ToolDefinition], file_tools: list[ToolDefinition]
) -> list[ToolDefinition]:
    """Merge inline and file-sourced tools, deduplicating by name."""
    seen: dict[str, ToolDefinition] = {}
    for t in inline:
        seen[t.name] = t
    for t in file_tools:
        if t.name not in seen:
            seen[t.name] = t
    return list(seen.values())


def run_pipeline(*, output_path: Path | None = None) -> dict:
    """Run the full analysis pipeline. Returns the output dict."""
    registry = load_agent_registry()

    if output_path is None:
        output_path = WEB_DATA_DIR / "analysis.json"

    prompts_out: list[dict] = []
    all_models: set[str] = set()
    all_agents: list[dict] = []
    all_vendors: set[str] = set()

    for agent_id, agent in registry.items():
        agent_name = agent["name"]
        vendor = agent.get("vendor", "Unknown")
        all_agents.append({"id": agent_id, "name": agent_name})
        all_vendors.add(vendor)

        # Parse separate tool files for this agent
        file_tools: list[ToolDefinition] = []
        for tool_entry in agent.get("tools", []):
            tool_path = DATA_DIR / tool_entry["path"]
            if tool_path.exists():
                fmt = tool_entry.get("format", "json")
                file_tools.extend(_parse_tool_file(tool_path, fmt))

        # Process each prompt
        for prompt_entry in agent.get("prompts", []):
            prompt_path = DATA_DIR / prompt_entry["path"]
            if not prompt_path.exists():
                continue

            fmt = prompt_entry.get("format", "txt")
            parsed, inline_tools = _parse_prompt_file(prompt_path, fmt)
            merged_tools = _merge_tools(inline_tools, file_tools)

            metrics = compute_metrics(parsed)
            tool_metrics = compute_tool_metrics(merged_tools)

            model = prompt_entry.get("model")
            if model:
                all_models.add(model)

            prompts_out.append({
                "agent_id": agent_id,
                "agent_name": agent_name,
                "vendor": vendor,
                "label": prompt_entry["label"],
                "model": model,
                "is_latest": prompt_entry.get("latest", False),
                "metrics": metrics,
                "tools": tool_metrics,
            })

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "llm_model": None,
            "agent_count": len(all_agents),
            "prompt_count": len(prompts_out),
        },
        "prompts": prompts_out,
        "filters": {
            "models": sorted(all_models),
            "agents": all_agents,
            "vendors": sorted(all_vendors),
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="System Prompts Analyzer")
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output JSON path (default: web/data/analysis.json)",
    )
    parser.add_argument("--skip-llm", action="store_true", default=True)
    args = parser.parse_args()

    result = run_pipeline(output_path=args.output)
    count = result["meta"]["prompt_count"]
    agents = result["meta"]["agent_count"]
    print(f"Analyzed {count} prompts from {agents} agents -> {args.output or WEB_DATA_DIR / 'analysis.json'}")


if __name__ == "__main__":
    main()
```

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All pass.

**Step 3: Run pipeline and inspect output**

```bash
uv run python -m spa.pipeline --skip-llm
cat web/data/analysis.json | python -m json.tool | head -50
```

Expected: Valid JSON with 9 agents and ~24 prompts.

**Step 4: Commit**

```bash
git add src/spa/pipeline.py tests/test_pipeline.py
git commit -m "Add analysis pipeline with CLI entry point"
```

---

### Task 7: Web scaffold - index.html, Pico CSS, Preact, Chart.js

**Files:**
- Create: `web/index.html`
- Create: `web/css/style.css`
- Create: `web/js/app.js`
- Create: `web/js/state.js`

**Step 1: Create index.html with CDN imports**

```html
<!-- web/index.html -->
<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>System Prompts Analyzer</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
  <link rel="stylesheet" href="css/style.css">
</head>
<body>
  <nav class="container">
    <ul><li><strong><a href="#/">System Prompts Analyzer</a></strong></li></ul>
    <ul>
      <li><a href="#/">Dashboard</a></li>
      <li><a href="#/compare">Compare</a></li>
    </ul>
  </nav>
  <main class="container" id="app">
    <p>Loading...</p>
  </main>
  <script type="module" src="https://esm.sh/preact@10"></script>
  <script type="module" src="https://esm.sh/htm@3/preact"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <script type="module" src="js/app.js"></script>
</body>
</html>
```

**Step 2: Create base CSS**

```css
/* web/css/style.css */
:root {
  --category-identity: #6366f1;
  --category-tone: #8b5cf6;
  --category-safety: #ef4444;
  --category-tools: #3b82f6;
  --category-workflow: #10b981;
  --category-examples: #f59e0b;
  --category-other: #6b7280;
}

.filter-bar {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 1rem;
}

.filter-bar select {
  min-width: 150px;
}

.metric-card {
  text-align: center;
  padding: 1rem;
}

.metric-card .value {
  font-size: 2rem;
  font-weight: bold;
}

.metric-card .label {
  font-size: 0.85rem;
  color: var(--pico-muted-color);
}

.category-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: white;
}

.category-badge.identity { background: var(--category-identity); }
.category-badge.tone { background: var(--category-tone); }
.category-badge.safety { background: var(--category-safety); }
.category-badge.tools { background: var(--category-tools); }
.category-badge.workflow { background: var(--category-workflow); }
.category-badge.examples { background: var(--category-examples); }
.category-badge.other { background: var(--category-other); }

.variant-row { font-size: 0.9rem; }
.variant-row td:first-child { padding-left: 2rem; }

table .sortable { cursor: pointer; user-select: none; }
table .sortable:hover { text-decoration: underline; }
table .sort-asc::after { content: " ▲"; }
table .sort-desc::after { content: " ▼"; }

.compare-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.chart-container {
  position: relative;
  max-height: 400px;
}

@media (max-width: 768px) {
  .compare-grid { grid-template-columns: 1fr; }
  .filter-bar { flex-direction: column; }
}
```

**Step 3: Create state manager**

```javascript
// web/js/state.js
// Filter state management

let _data = null;
let _filters = { agents: [], vendors: [], models: [] };
let _listeners = [];

export async function loadData() {
  const resp = await fetch('data/analysis.json');
  _data = await resp.json();
  _notify();
  return _data;
}

export function getData() { return _data; }

export function getFilters() { return { ..._filters }; }

export function setFilter(key, values) {
  _filters[key] = values;
  _notify();
}

export function getFilteredPrompts() {
  if (!_data) return [];
  return _data.prompts.filter(p => {
    if (_filters.agents.length && !_filters.agents.includes(p.agent_id)) return false;
    if (_filters.vendors.length && !_filters.vendors.includes(p.vendor)) return false;
    if (_filters.models.length && !_filters.models.includes(p.model)) return false;
    return true;
  });
}

export function subscribe(fn) {
  _listeners.push(fn);
  return () => { _listeners = _listeners.filter(l => l !== fn); };
}

function _notify() { _listeners.forEach(fn => fn()); }
```

**Step 4: Create hash router and app shell**

```javascript
// web/js/app.js
import { loadData, subscribe } from './state.js';

const routes = {};
let currentCleanup = null;

export function registerRoute(pattern, handler) {
  routes[pattern] = handler;
}

function matchRoute(hash) {
  const path = hash.replace(/^#/, '') || '/';
  for (const [pattern, handler] of Object.entries(routes)) {
    // Simple pattern matching: /agent/:id -> regex
    const regex = new RegExp('^' + pattern.replace(/:(\w+)/g, '(?<$1>[^/]+)') + '$');
    const match = path.match(regex);
    if (match) return { handler, params: match.groups || {} };
  }
  return null;
}

function navigate() {
  if (currentCleanup) { currentCleanup(); currentCleanup = null; }
  const app = document.getElementById('app');
  const result = matchRoute(location.hash);
  if (result) {
    currentCleanup = result.handler(app, result.params) || null;
  } else {
    app.innerHTML = '<p>Page not found. <a href="#/">Go to dashboard</a></p>';
  }
}

// Dynamic imports for views - loaded after data is ready
async function init() {
  await loadData();

  const { renderDashboard } = await import('./views/dashboard.js');
  const { renderAgentDetail } = await import('./views/agent-detail.js');
  const { renderCompare } = await import('./views/compare.js');

  registerRoute('/', renderDashboard);
  registerRoute('/agent/:id', renderAgentDetail);
  registerRoute('/compare', renderCompare);

  window.addEventListener('hashchange', navigate);
  navigate();
}

init();
```

**Step 5: Commit**

```bash
git add web/index.html web/css/style.css web/js/app.js web/js/state.js
git commit -m "Add web scaffold with Preact/HTM, router, and state management"
```

---

### Task 8: Dashboard view

**Files:**
- Create: `web/js/views/dashboard.js`
- Create: `web/js/components/filter-bar.js`
- Create: `web/js/components/chart.js`
- Create: `web/js/components/table.js`

**Step 1: Create filter bar component**

```javascript
// web/js/components/filter-bar.js
import { getData, getFilters, setFilter } from '../state.js';

export function renderFilterBar(container) {
  const data = getData();
  if (!data) return;

  const filters = data.filters;
  const current = getFilters();

  container.innerHTML = `
    <div class="filter-bar">
      <select id="filter-agent" multiple size="1">
        <option value="">All Agents</option>
        ${filters.agents.map(a =>
          `<option value="${a.id}" ${current.agents.includes(a.id) ? 'selected' : ''}>${a.name}</option>`
        ).join('')}
      </select>
      <select id="filter-vendor" multiple size="1">
        <option value="">All Vendors</option>
        ${filters.vendors.map(v =>
          `<option value="${v}" ${current.vendors.includes(v) ? 'selected' : ''}>${v}</option>`
        ).join('')}
      </select>
      <select id="filter-model" multiple size="1">
        <option value="">All Models</option>
        ${filters.models.map(m =>
          `<option value="${m}" ${current.models.includes(m) ? 'selected' : ''}>${m}</option>`
        ).join('')}
      </select>
    </div>
  `;

  // Bind change events
  for (const [id, key] of [['filter-agent', 'agents'], ['filter-vendor', 'vendors'], ['filter-model', 'models']]) {
    container.querySelector(`#${id}`).addEventListener('change', (e) => {
      const selected = [...e.target.selectedOptions]
        .map(o => o.value)
        .filter(v => v !== '');
      setFilter(key, selected);
    });
  }
}
```

**Step 2: Create chart helpers**

```javascript
// web/js/components/chart.js

let _charts = {};

export function destroyChart(id) {
  if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

export function createBarChart(canvasId, labels, datasets, options = {}) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  _charts[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...options,
    },
  });
  return _charts[canvasId];
}

export function createRadarChart(canvasId, labels, datasets, options = {}) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  _charts[canvasId] = new Chart(ctx, {
    type: 'radar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...options,
    },
  });
  return _charts[canvasId];
}

export function destroyAll() {
  Object.keys(_charts).forEach(destroyChart);
}
```

**Step 3: Create sortable table component**

```javascript
// web/js/components/table.js

export function renderSortableTable(container, { columns, rows, onRowClick, groupBy }) {
  let sortCol = columns[0]?.key;
  let sortDir = 'asc';

  function render() {
    // Group rows if groupBy is specified
    let displayRows = [...rows];
    if (sortCol) {
      displayRows.sort((a, b) => {
        const av = a[sortCol], bv = b[sortCol];
        const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv));
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }

    const thead = columns.map(c => {
      const cls = c.key === sortCol ? `sortable sort-${sortDir}` : 'sortable';
      return `<th class="${cls}" data-col="${c.key}">${c.label}</th>`;
    }).join('');

    const tbody = displayRows.map((row, i) => {
      const cls = row._isVariant ? 'variant-row' : '';
      const cells = columns.map(c => `<td>${row[c.key] ?? ''}</td>`).join('');
      return `<tr class="${cls}" data-idx="${i}">${cells}</tr>`;
    }).join('');

    container.innerHTML = `
      <figure>
        <table role="grid">
          <thead><tr>${thead}</tr></thead>
          <tbody>${tbody}</tbody>
        </table>
      </figure>
    `;

    // Bind sort clicks
    container.querySelectorAll('th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (col === sortCol) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }
        else { sortCol = col; sortDir = 'asc'; }
        render();
      });
    });

    // Bind row clicks
    if (onRowClick) {
      container.querySelectorAll('tbody tr').forEach(tr => {
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => {
          const idx = parseInt(tr.dataset.idx);
          onRowClick(displayRows[idx]);
        });
      });
    }
  }

  render();
}
```

**Step 4: Create dashboard view**

```javascript
// web/js/views/dashboard.js
import { getFilteredPrompts, getData, subscribe } from '../state.js';
import { renderFilterBar } from '../components/filter-bar.js';
import { createBarChart, destroyAll } from '../components/chart.js';
import { renderSortableTable } from '../components/table.js';

export function renderDashboard(app) {
  function render() {
    const prompts = getFilteredPrompts();
    const data = getData();

    app.innerHTML = `
      <h2>Dashboard</h2>
      <div id="filter-container"></div>
      <div class="grid">
        <div class="metric-card"><div class="value">${data.meta.agent_count}</div><div class="label">Agents</div></div>
        <div class="metric-card"><div class="value">${prompts.length}</div><div class="label">Prompts</div></div>
        <div class="metric-card"><div class="value">${data.filters.models.length}</div><div class="label">Models</div></div>
      </div>
      <div class="chart-container" style="height:300px"><canvas id="size-chart"></canvas></div>
      <div id="table-container"></div>
    `;

    renderFilterBar(document.getElementById('filter-container'));

    // Bar chart: word counts
    const labels = prompts.map(p => `${p.agent_name} (${p.label})`);
    const wordCounts = prompts.map(p => p.metrics.word_count);
    createBarChart('size-chart', labels, [{
      label: 'Word Count',
      data: wordCounts,
      backgroundColor: '#3b82f6',
    }]);

    // Table
    const rows = prompts.map(p => ({
      agent: p.agent_name,
      label: p.label,
      model: p.model || '-',
      words: p.metrics.word_count,
      sections: p.metrics.section_count,
      tools: p.tools.count,
      directives: p.metrics.directive_count,
      format: p.metrics.format_type,
      _agentId: p.agent_id,
    }));

    renderSortableTable(document.getElementById('table-container'), {
      columns: [
        { key: 'agent', label: 'Agent' },
        { key: 'label', label: 'Variant' },
        { key: 'model', label: 'Model' },
        { key: 'words', label: 'Words' },
        { key: 'sections', label: 'Sections' },
        { key: 'tools', label: 'Tools' },
        { key: 'directives', label: 'Directives' },
        { key: 'format', label: 'Format' },
      ],
      rows,
      onRowClick: (row) => { location.hash = `#/agent/${row._agentId}`; },
    });
  }

  render();
  const unsub = subscribe(render);
  return () => { unsub(); destroyAll(); };
}
```

**Step 5: Verify in browser**

```bash
uv run python -m spa.pipeline --skip-llm
python3 -m http.server 8000 --directory web &
```

Open http://localhost:8000 - should see dashboard with chart and sortable table.

**Step 6: Commit**

```bash
git add web/js/views/dashboard.js web/js/components/
git commit -m "Add dashboard view with filter bar, chart, and sortable table"
```

---

### Task 9: Agent detail view

**Files:**
- Create: `web/js/views/agent-detail.js`

**Step 1: Implement agent detail view**

```javascript
// web/js/views/agent-detail.js
import { getData, subscribe } from '../state.js';
import { createRadarChart, destroyAll } from '../components/chart.js';

function computeAverages(prompts) {
  const n = prompts.length || 1;
  const sum = (key) => prompts.reduce((s, p) => s + (p.metrics[key] || 0), 0) / n;
  return {
    word_count: Math.round(sum('word_count')),
    section_count: Math.round(sum('section_count')),
    directive_count: Math.round(sum('directive_count')),
    example_count: Math.round(sum('example_count')),
    directive_density: Math.round(sum('directive_density') * 10) / 10,
  };
}

function renderMetricsPanel(metrics) {
  return `
    <div class="grid">
      <div class="metric-card"><div class="value">${metrics.word_count}</div><div class="label">Words</div></div>
      <div class="metric-card"><div class="value">${metrics.line_count}</div><div class="label">Lines</div></div>
      <div class="metric-card"><div class="value">${metrics.section_count}</div><div class="label">Sections</div></div>
      <div class="metric-card"><div class="value">${metrics.directive_count}</div><div class="label">Directives</div></div>
      <div class="metric-card"><div class="value">${metrics.directive_density}</div><div class="label">Dir/1K Words</div></div>
      <div class="metric-card"><div class="value">${metrics.example_count}</div><div class="label">Examples</div></div>
    </div>
  `;
}

function renderSectionsList(metrics) {
  const cats = metrics.sections_by_category || {};
  return Object.entries(cats).map(([cat, count]) =>
    `<span class="category-badge ${cat}">${cat}: ${count}</span>`
  ).join(' ');
}

function renderToolsList(tools) {
  if (!tools.names.length) return '<p>No tools found.</p>';
  return `
    <p><strong>${tools.count} tools</strong>
      (${Object.entries(tools.sources || {}).map(([k, v]) => `${v} ${k}`).join(', ')})</p>
    <details>
      <summary>Tool list</summary>
      <ul>${tools.names.map(n => `<li>${n}</li>`).join('')}</ul>
    </details>
    ${Object.keys(tools.categories || {}).length ? `
      <details>
        <summary>Categories</summary>
        <ul>${Object.entries(tools.categories).map(([cat, names]) =>
          `<li><strong>${cat}:</strong> ${names.join(', ')}</li>`
        ).join('')}</ul>
      </details>
    ` : ''}
  `;
}

export function renderAgentDetail(app, { id }) {
  const data = getData();
  const agentPrompts = data.prompts.filter(p => p.agent_id === id);
  if (!agentPrompts.length) {
    app.innerHTML = `<p>Agent "${id}" not found. <a href="#/">Back</a></p>`;
    return;
  }

  const agent = agentPrompts[0];
  const averages = computeAverages(data.prompts);

  app.innerHTML = `
    <nav aria-label="breadcrumb"><ul><li><a href="#/">Dashboard</a></li><li>${agent.agent_name}</li></ul></nav>
    <hgroup>
      <h2>${agent.agent_name}</h2>
      <p>${agent.vendor} - ${agentPrompts.length} variant(s)</p>
    </hgroup>

    <div role="tablist">
      ${agentPrompts.map((p, i) => `
        <button role="tab" class="outline ${i === 0 ? 'contrast' : 'secondary'}"
                data-idx="${i}">${p.label}${p.model ? ` (${p.model})` : ''}</button>
      `).join(' ')}
    </div>

    <div id="variant-content"></div>

    <h3>Radar: This Agent vs Average</h3>
    <div class="chart-container" style="height:350px"><canvas id="radar-chart"></canvas></div>
  `;

  function showVariant(idx) {
    const p = agentPrompts[idx];
    document.getElementById('variant-content').innerHTML = `
      <article>
        <header><strong>${p.label}</strong>${p.model ? ` - Model: ${p.model}` : ''} ${p.is_latest ? '(latest)' : ''}</header>
        ${renderMetricsPanel(p.metrics)}
        <h4>Sections</h4>
        ${renderSectionsList(p.metrics)}
        <h4>Tools</h4>
        ${renderToolsList(p.tools)}
        <h4>Top Directives</h4>
        <ul>${Object.entries(p.metrics.directive_keywords || {})
          .sort(([, a], [, b]) => b - a)
          .slice(0, 5)
          .map(([kw, count]) => `<li><strong>${kw}</strong>: ${count}</li>`)
          .join('')}</ul>
      </article>
    `;

    // Update tab styles
    app.querySelectorAll('[role="tab"]').forEach((btn, i) => {
      btn.className = `outline ${i === idx ? 'contrast' : 'secondary'}`;
    });
  }

  // Tab click handlers
  app.querySelectorAll('[role="tab"]').forEach(btn => {
    btn.addEventListener('click', () => showVariant(parseInt(btn.dataset.idx)));
  });

  showVariant(0);

  // Radar chart: latest prompt vs averages
  const latest = agentPrompts.find(p => p.is_latest) || agentPrompts[0];
  const radarLabels = ['Words/100', 'Sections', 'Directives', 'Dir Density', 'Examples', 'Tools'];
  createRadarChart('radar-chart', radarLabels, [
    {
      label: agent.agent_name,
      data: [
        latest.metrics.word_count / 100,
        latest.metrics.section_count,
        latest.metrics.directive_count,
        latest.metrics.directive_density,
        latest.metrics.example_count,
        latest.tools.count,
      ],
      borderColor: '#3b82f6',
      backgroundColor: 'rgba(59,130,246,0.1)',
    },
    {
      label: 'Average',
      data: [
        averages.word_count / 100,
        averages.section_count,
        averages.directive_count,
        averages.directive_density,
        averages.example_count,
        Math.round(data.prompts.reduce((s, p) => s + p.tools.count, 0) / data.prompts.length),
      ],
      borderColor: '#6b7280',
      backgroundColor: 'rgba(107,114,128,0.1)',
    },
  ]);

  return () => destroyAll();
}
```

**Step 2: Verify in browser**

Click any agent row in dashboard. Should show tabbed variants, metrics, radar chart.

**Step 3: Commit**

```bash
git add web/js/views/agent-detail.js
git commit -m "Add agent detail view with variant tabs and radar chart"
```

---

### Task 10: Compare view

**Files:**
- Create: `web/js/views/compare.js`

**Step 1: Implement compare view**

```javascript
// web/js/views/compare.js
import { getData } from '../state.js';
import { createRadarChart, destroyAll } from '../components/chart.js';

function promptKey(p) { return `${p.agent_id}::${p.label}`; }

function metricDelta(a, b) {
  const diff = a - b;
  if (diff === 0) return `${a}`;
  const sign = diff > 0 ? '+' : '';
  return `${a} <small>(${sign}${diff})</small>`;
}

export function renderCompare(app) {
  const data = getData();
  const prompts = data.prompts;

  // Parse URL params
  const hash = location.hash.replace('#/compare', '');
  const params = new URLSearchParams(hash.startsWith('?') ? hash : '');
  let keyA = params.get('a') || '';
  let keyB = params.get('b') || '';

  function render() {
    const pA = prompts.find(p => promptKey(p) === keyA);
    const pB = prompts.find(p => promptKey(p) === keyB);

    const options = prompts.map(p => {
      const k = promptKey(p);
      return `<option value="${k}">${p.agent_name} - ${p.label}</option>`;
    }).join('');

    app.innerHTML = `
      <h2>Compare Prompts</h2>
      <div class="grid">
        <select id="sel-a"><option value="">Select prompt A</option>${options}</select>
        <select id="sel-b"><option value="">Select prompt B</option>${options}</select>
      </div>
      <div id="compare-content"></div>
    `;

    const selA = document.getElementById('sel-a');
    const selB = document.getElementById('sel-b');
    selA.value = keyA;
    selB.value = keyB;

    selA.addEventListener('change', () => {
      keyA = selA.value;
      location.hash = `#/compare?a=${encodeURIComponent(keyA)}&b=${encodeURIComponent(keyB)}`;
      renderComparison();
    });
    selB.addEventListener('change', () => {
      keyB = selB.value;
      location.hash = `#/compare?a=${encodeURIComponent(keyA)}&b=${encodeURIComponent(keyB)}`;
      renderComparison();
    });

    renderComparison();
  }

  function renderComparison() {
    const container = document.getElementById('compare-content');
    const pA = prompts.find(p => promptKey(p) === keyA);
    const pB = prompts.find(p => promptKey(p) === keyB);

    if (!pA || !pB) {
      container.innerHTML = '<p>Select two prompts to compare.</p>';
      return;
    }

    const mA = pA.metrics, mB = pB.metrics;
    const metrics = [
      ['Words', mA.word_count, mB.word_count],
      ['Lines', mA.line_count, mB.line_count],
      ['Sections', mA.section_count, mB.section_count],
      ['Directives', mA.directive_count, mB.directive_count],
      ['Dir. Density', mA.directive_density, mB.directive_density],
      ['Examples', mA.example_count, mB.example_count],
      ['Tools', pA.tools.count, pB.tools.count],
      ['Format', mA.format_type, mB.format_type],
    ];

    container.innerHTML = `
      <div class="compare-grid">
        <article>
          <header><strong>${pA.agent_name}</strong> - ${pA.label}</header>
          <p>Vendor: ${pA.vendor} | Model: ${pA.model || '-'}</p>
        </article>
        <article>
          <header><strong>${pB.agent_name}</strong> - ${pB.label}</header>
          <p>Vendor: ${pB.vendor} | Model: ${pB.model || '-'}</p>
        </article>
      </div>
      <figure>
        <table>
          <thead><tr><th>Metric</th><th>${pA.agent_name}</th><th>${pB.agent_name}</th></tr></thead>
          <tbody>
            ${metrics.map(([label, a, b]) => `
              <tr>
                <td>${label}</td>
                <td>${typeof a === 'number' ? metricDelta(a, a - b) : a}</td>
                <td>${typeof b === 'number' ? metricDelta(b, b - a) : b}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </figure>
      <div class="chart-container" style="height:350px"><canvas id="compare-radar"></canvas></div>
    `;

    const labels = ['Words/100', 'Sections', 'Directives', 'Dir Density', 'Examples', 'Tools'];
    createRadarChart('compare-radar', labels, [
      {
        label: `${pA.agent_name} (${pA.label})`,
        data: [mA.word_count / 100, mA.section_count, mA.directive_count, mA.directive_density, mA.example_count, pA.tools.count],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.1)',
      },
      {
        label: `${pB.agent_name} (${pB.label})`,
        data: [mB.word_count / 100, mB.section_count, mB.directive_count, mB.directive_density, mB.example_count, pB.tools.count],
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.1)',
      },
    ]);
  }

  render();
  return () => destroyAll();
}
```

**Step 2: Verify in browser**

Navigate to `#/compare`, select two prompts. Should see side-by-side table and overlaid radar chart.

**Step 3: Commit**

```bash
git add web/js/views/compare.js
git commit -m "Add compare view with side-by-side metrics and radar overlay"
```

---

### Task 11: End-to-end verification

**Step 1: Run full pipeline**

```bash
uv run python -m spa.pipeline --skip-llm
```

Expected: Outputs path and counts.

**Step 2: Run all tests**

```bash
uv run pytest -v
```

Expected: All tests pass.

**Step 3: Lint**

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

Expected: No errors.

**Step 4: Manual browser test**

```bash
python3 -m http.server 8000 --directory web
```

Check:
- Dashboard loads with chart + table
- Filters work (agent, vendor, model dropdowns)
- Clicking table row navigates to agent detail
- Agent detail shows tabs for variants
- Compare view works with two selected prompts
- Sort columns work in dashboard table

**Step 5: Commit**

```bash
git add -A
git commit -m "Phase 1 complete: rule-based pipeline and web UI"
```
