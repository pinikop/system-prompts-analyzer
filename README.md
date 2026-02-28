# System Prompts Analyzer

> Analyze coding assistant system prompts with quantitative metrics and LLM-powered thematic insights

## About the Data Source

[system-prompts-and-models-of-ai-tools](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools) is a community repository collecting system prompts from 30+ AI coding assistants (Claude Code, Cursor, Copilot, Windsurf, etc.). It provides raw prompt files showing how each tool is instructed to behave.

## What This Analyzer Does

This tool processes those prompts to extract insights:

- **Quantitative metrics**: word count, directives (NEVER, MUST), sections, examples
- **Tool usage patterns**: categorized tools (file operations, search, execution, web, AI)
- **LLM-powered thematic analysis**: identity, tone, safety emphasis, autonomy level, coding philosophy
- **Interactive web dashboard**: compare assistants, filter by vendor/model, drill into details

## Quick Start

```bash
# 1. Install dependencies (requires Python 3.12+, uv)
uv sync --extra llm

# 2. Configure LLM provider
cp .env.example .env
# Add your LLM_API_KEY to .env

# 3. Run the pipeline
uv run spa

# 4. View results
# Open web/index.html in your browser
```

## What You Get

### Rule-Based Metrics
- Word count, line count, character count
- Directive keywords (NEVER, MUST, DO NOT, IMPORTANT)
- Section count and format type detection
- Example count and directive density

### Tool Analysis
- Tool counting and categorization
- Categories: file_ops, search, execution, web, ai, git, test, debug, docs

### LLM Thematic Analysis
- Identity: how the assistant describes itself
- Tone: formal, casual, technical, friendly
- Personality: traits and characteristics
- Safety emphasis: paranoid, high, moderate, minimal
- Autonomy level: asks permission vs. acts independently
- Coding philosophy: testing approach, error handling, documentation style

### Web Dashboard
- **Dashboard** (`/`): Overview of all assistants with metrics comparison
- **Detail View** (`/assistant/:id`): Deep dive into one assistant's prompts and history
- **Compare** (`/compare`): Side-by-side comparison of selected assistants
- **Filter Bar**: Filter by vendor, assistant, model

### JSON Output
- `web/data/analysis.json`: Complete analysis results
- Schema: assistants, metrics, tools, LLM analysis, metadata
- Generated timestamp and token usage stats

## Usage

### CLI Flags

```bash
# Full analysis (metrics + LLM)
uv run spa

# Skip LLM analysis (faster, no API key needed)
uv run spa --skip-llm

# Force reprocess everything (ignore cache)
uv run spa --force

# Use local data only (skip upstream updates)
uv run spa --skip-update

# Custom LLM model
uv run spa --llm-model gpt-4o
```

### Common Workflows

**First time setup:**
```bash
uv sync --extra llm
cp .env.example .env
# Edit .env to add LLM_API_KEY
uv run spa
```

**Quick metrics without LLM:**
```bash
uv run spa --skip-llm
```

**Update data and reprocess:**
```bash
git submodule update --remote data
uv run spa --force
```

**Local development (offline):**
```bash
uv run spa --skip-update --skip-llm
```

## How It Works

### Architecture

**Pipeline:** `agents.yaml → parse prompts → compute metrics → optional LLM analysis → analysis.json`

**Key Components:**

- **agents.yaml**: Registry mapping assistants to prompt files and tool definitions. Defines which prompts are "current" vs. historical.

- **Python pipeline** (`src/spa/`):
  - Parsers: Extract structured data from prompt files (txt/yaml) and tool files (json/txt)
  - Metrics: Compute quantitative metrics (word count, directives, sections)
  - LLM: Optional thematic analysis via litellm (requires API key)
  - Pipeline orchestrator: Reads registry, runs analysis, writes JSON

- **Web dashboard** (`web/`):
  - Static vanilla JavaScript SPA
  - Hash-based router with 3 routes
  - Pico CSS (classless) with minimal custom styling
  - Reads `analysis.json` and provides filtering/comparison UI

- **Data submodule** (`data/`):
  - Git submodule pointing to x1xhlol's repository
  - 30,000+ lines of prompts from AI coding assistants
  - Updated independently from this analyzer

### Data Flow

```
1. agents.yaml defines assistants and prompt file paths
2. Pipeline reads prompt files from data/ submodule
3. Parsers extract text and structure
4. Metrics module computes quantitative data
5. LLM module (optional) extracts thematic insights
6. Pipeline writes analysis.json
7. Web dashboard reads JSON and renders UI
```

### Incremental Processing

The pipeline caches LLM results in `analysis.json` via `cache_info.file_hashes`. On subsequent runs:
- Unchanged files reuse their cached LLM analysis (skipping API calls)
- Changed files are reprocessed
- Use `--force` to bypass the cache and reprocess everything

## Configuration

### LLM Providers

**Default (Nebius-hosted Qwen):**
```bash
# .env
LLM_API_KEY=your-nebius-api-key
```

**OpenAI:**
```bash
# .env
LLM_API_KEY=sk-proj-abc123...
LLM_BASE_URL=https://api.openai.com/v1/
```
Then run:
```bash
uv run spa --llm-model gpt-4o
```

**Anthropic:**
```bash
# .env
LLM_API_KEY=sk-ant-abc123...
LLM_BASE_URL=https://api.anthropic.com/v1/
```
Then run:
```bash
uv run spa --llm-model claude-sonnet-4
```

**Any OpenAI-compatible API:**
```bash
# .env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://your-endpoint.com/v1/
```

### Cache Control

- **Default**: Incremental processing (reuse cached LLM results for unchanged files)
- **Force reprocess**: `uv run spa --force`
- **Cache location**: `web/data/analysis.json` (contains `cache_info.file_hashes`)

### Data Source

- **Location**: `data/` directory (git submodule)
- **Update**: `git submodule update --remote data`
- **Skip updates**: `uv run spa --skip-update` (use local data only)
- **Upstream**: https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools

## Development

### Setup

```bash
# Install dependencies (includes LLM extras)
uv sync --extra llm

# Install without LLM support (metrics only)
uv sync
```

### Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_metrics.py

# Run specific test
uv run pytest tests/test_metrics.py -k test_word_count

# Verbose output
uv run pytest -v
```

### Linting and Formatting

```bash
# Check code style
uv run ruff check src tests

# Format code
uv run ruff format src tests

# Check formatting without changes
uv run ruff format --check src tests
```

### File Structure

```
├── agents.yaml              # Assistant registry (maps assistants to prompt files)
├── src/spa/                 # Python pipeline
│   ├── config.py           # Paths, constants, directive keywords
│   ├── pipeline.py         # Orchestrator (main entry point)
│   ├── parsers/            # Prompt and tool file parsers
│   ├── metrics/            # Rule-based metrics computation
│   └── llm/                # Optional LLM-powered analysis
├── web/                     # Static web dashboard
│   ├── index.html          # Entry point
│   ├── js/app.js           # Router and initialization
│   ├── js/state.js         # Global state and filters
│   ├── js/views/           # Page renderers (dashboard, detail, compare)
│   ├── js/components/      # Reusable UI (chart, table, filter bar)
│   └── data/analysis.json  # Pipeline output (generated)
├── data/                    # Git submodule (prompt data)
├── tests/                   # Test suite
└── docs/plans/              # Design docs and implementation plans
```

### Key Files

- **agents.yaml**: Defines all coding assistants, their prompt file paths, and which versions are "current"
- **web/data/analysis.json**: Pipeline output consumed by the web UI (the contract between pipeline and UI)
- **src/spa/data_source.py**: File hashing and cache metadata utilities
- **CLAUDE.md**: Detailed guidance for Claude Code when working in this repository

## Credits

This project analyzes prompts from [system-prompts-and-models-of-ai-tools](https://github.com/x1xhlol/system-prompts-and-models-of-ai-tools) by [@x1xhlol](https://github.com/x1xhlol).

**Data source (GPL-3.0):**
- 30,000+ lines of AI tool system prompts
- Actively maintained community repository
- Tracks prompts from Claude Code, Cursor, Copilot, Windsurf, Codeium, Aide, Continue, and more
- Latest update: 08/01/2026

**This analyzer:** MIT License
