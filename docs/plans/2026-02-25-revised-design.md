# System Prompts Analyzer - Revised Design

## Context

Analyze leaked system prompts from 9 AI coding agents. Python pipeline produces `analysis.json`, static web UI renders it.

**Data source**: git submodule at `data/` pointing to `x1xhlol/system-prompts-and-models-of-ai-tools`.

**Agents**: Claude Code, Cursor, Windsurf, Devin AI, Augment Code, VSCode Copilot, Replit, Kiro, Amp.

## Key Changes from Original Plan

1. **Two-axis data model (agent x model)** - prompts tagged with target model for cross-cutting comparisons
2. **Inline tool extraction** - tools are embedded in prompt text for all 9 agents; separate tool files are supplementary
3. **Section classification** - sections categorized (identity, tone, safety, tools, workflow, examples)
4. **Phase reorder** - full UI before LLM analysis
5. **Preact + HTM** - component-based UI via CDN, no build step

## Data Model

Each analysis entry is a **prompt** identified by `(agent_id, model, label)`.

`agents.yaml` schema per prompt entry:
- `label`: display name (e.g., "Agent 2.0", "Claude Sonnet 4")
- `path`: file path relative to `data/`
- `model`: target LLM model or null for generic prompts
- `format`: "yaml" for Amp, omit for txt (default)
- `latest`: true for the version used in LLM analysis

Output JSON is a flat list of prompt entries with convenience lookup arrays for filters.

## Architecture

```
agents.yaml + data/
    |
    v
Python pipeline (parse -> classify -> metrics -> JSON)
    |
    v
web/data/analysis.json
    |
    v
Static web UI (Preact + HTM + Chart.js + Pico CSS)
```

## Parsers

### txt_parser (handles ~80% of files)
- Pass 1: extract XML sections (tags with >50 chars content)
- Pass 2: split by markdown headings
- Pass 3 (new): extract inline tool definitions
  - JSON schema blocks (`"name"` + `"description"` keys)
  - TypeScript type declarations (`type name = ...`)
  - XML tool blocks with parameter descriptions

### yaml_parser (Amp)
- Extract text from YAML `system[].text` structure
- Delegate to txt_parser for section extraction

### json_parser (separate tool files)
- Parse `{"tools": [...]}` or bare array format
- Flag as `source: "file"`

### Section classifier
- Categorize sections by keyword matching on name + first 100 chars:
  - identity, tone, safety, tools, workflow, examples, other

## Metrics (per prompt)

- Word count, line count, character count
- Section count (total and by category)
- Directive keyword frequencies (NEVER, MUST, ALWAYS, DO NOT, IMPORTANT, CRITICAL, REQUIRED, FORBIDDEN, PROHIBITED, MANDATORY)
- Directive density (directives per 1000 words)
- Example count
- Format type (markdown, xml, mixed, plain, yaml)
- Tool count (inline + file), tool names, tool categories

## Pipeline

```
Load agents.yaml
  -> For each agent, for each prompt:
       Parse prompt text
       Extract inline tools
       Classify sections
       Compute metrics
  -> For each agent's tool files:
       Parse and merge with inline tools (dedupe by name)
  -> Write web/data/analysis.json
  -> (Phase 2: LLM analysis on latest prompts only)
```

CLI: `uv run spa --skip-llm` | `uv run spa --model openai/deepseek-r1`

## Output JSON Schema

```json
{
  "generated_at": "ISO timestamp",
  "meta": {
    "llm_model": null,
    "agent_count": 9,
    "prompt_count": 24
  },
  "prompts": [
    {
      "agent_id": "vscode-copilot",
      "agent_name": "VSCode Agent (Copilot)",
      "vendor": "Microsoft",
      "label": "GPT-5",
      "model": "gpt-5",
      "is_latest": true,
      "metrics": {
        "word_count": 2923,
        "line_count": 404,
        "char_count": 18500,
        "section_count": 12,
        "sections_by_category": {"safety": 3, "tools": 4, "identity": 1, "other": 4},
        "directive_keywords": {"NEVER": 5, "MUST": 3},
        "directive_count": 8,
        "directive_density": 2.7,
        "example_count": 2,
        "format_type": "mixed"
      },
      "tools": {
        "count": 15,
        "names": ["Bash", "Read", "Write"],
        "categories": {"file_ops": ["Read", "Write"], "execution": ["Bash"]},
        "sources": {"inline": 12, "file": 3}
      }
    }
  ],
  "filters": {
    "models": ["gpt-5", "claude-sonnet-4", "gemini-2.5-pro"],
    "agents": [{"id": "claude-code", "name": "Claude Code"}],
    "vendors": ["Anthropic", "Anysphere", "Codeium", "Cognition", "Augment", "Microsoft", "Replit", "Amazon", "Sourcegraph"]
  }
}
```

## Web UI

**Stack**: Preact + HTM (CDN), Chart.js (CDN), Pico CSS (CDN). No build step.

### Dashboard (`#/`)
- Filter bar: Agent, Vendor, Model dropdowns (multi-select)
- Bar chart: prompt sizes for filtered set
- Sortable table: Agent | Label | Model | Words | Sections | Tools | Directives | Format
- Rows grouped by agent, expandable sub-rows for variants
- Click row -> agent detail

### Agent Detail (`#/agent/:id`)
- Header with agent name, vendor, variant count
- Tabs for each prompt variant
- Per-variant: metrics panel, section list (colored by category), tool list
- Radar chart: this agent's latest vs average

### Compare (`#/compare?a=X&b=Y`)
- Two prompt selectors (any prompt from any agent)
- Side-by-side metrics table with highlighted deltas
- Overlaid radar chart
- Section category breakdown

### UI Patterns
- Client-side filtering on loaded JSON
- Hash-based routing with bookmarkable URLs
- Responsive: table -> cards on mobile

## Phases

### Phase 1: Pipeline + Full UI (rule-based)
1. Update agents.yaml with model tags
2. Enhance parsers (inline tool extraction, section classification)
3. Implement metrics
4. Wire pipeline with --skip-llm
5. Build all web views (dashboard, detail, compare)
6. Verify: pipeline produces valid JSON, all views render

### Phase 2: LLM Analysis
7. Pydantic schemas for LLM structured output
8. Per-agent thematic analysis (latest prompts only)
9. Cross-agent comparison
10. Update pipeline and web views with LLM data

### Phase 3: Polish
11. Responsive design
12. Deploy (GitHub Pages)

## Project Structure

```
system-prompts-analyzer/
  pyproject.toml
  agents.yaml
  .env                          # LLM_API_KEY, LLM_BASE_URL (optional)
  data/                         # git submodule
  src/spa/
    config.py
    parsers/
      base.py
      txt_parser.py
      yaml_parser.py
      json_parser.py
      classifier.py             # Section classifier
    metrics/
      rule_based.py
      tool_metrics.py
    llm/
      analyzer.py
      schemas.py
    pipeline.py
    output.py
  web/
    index.html
    css/style.css
    js/
      app.js                    # Hash router, init, data loading
      state.js                  # Filter state management
      views/dashboard.js
      views/agent-detail.js
      views/compare.js
      components/filter-bar.js
      components/chart.js
      components/table.js
    data/analysis.json          # Generated (gitignored)
  tests/
  docs/plans/
```
