# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Terminology

- **Coding assistant**: The product (Claude Code, Cursor, Copilot, GitHub Copilot, Windsurf, etc.)
- **Prompt variant**: A specific system prompt for a coding assistant, possibly targeting a particular model (e.g., Copilot's GPT-4o prompt vs GPT-4.1 prompt)
- **Current**: The latest/active prompt variant(s) for a coding assistant
- Do NOT use "agent" to refer to coding assistants. The codebase uses `assistant_id` and `assistant_name`.

## Commands

- `uv run spa` - Run analysis pipeline (outputs `web/data/analysis.json`)
- `uv run spa --skip-llm` - Run pipeline without LLM analysis (no API key needed)
- `uv run pytest` - Run all tests
- `uv run pytest tests/test_metrics.py -k test_name` - Run a single test
- `uv run ruff check src tests` - Lint
- `uv run ruff format src tests` - Format

## Architecture

The system has two main parts connected by `analysis.json`:

**Python pipeline** (`src/spa/`): `agents.yaml` -> parse prompts -> compute metrics -> optional LLM analysis -> `web/data/analysis.json`

- `config.py` - Paths, constants, directive keywords, tool categories
- `pipeline.py` - Orchestrator: reads registry, parses files, computes metrics, runs LLM analysis, writes JSON
- `parsers/` - Parse prompt files (txt/yaml) and tool files (json/txt) into `ParsedPrompt` and `ToolDefinition` dataclasses (`base.py`)
- `metrics/rule_based.py` - Computes quantitative metrics from parsed prompts (word count, sections, directive density, etc.)
- `metrics/tool_metrics.py` - Categorizes and counts tools
- `llm/` - Optional LLM-powered thematic analysis via `litellm`. Requires `LLM_API_KEY` env var (and optionally `LLM_BASE_URL`). Install with `uv sync --extra llm`.

**Web dashboard** (`web/`): Static vanilla JS SPA reading `analysis.json`

- Hash-based router in `app.js` with three routes: `/` (dashboard), `/assistant/:id` (detail), `/compare`
- `state.js` - Global data store with filter state and pub/sub for reactivity
- `views/` - Page renderers; `components/` - Reusable UI (chart, table, filter bar)
- Uses Pico CSS (classless) with minimal custom CSS

**Data flow**: `agents.yaml` defines coding assistants and maps them to prompt files in `data/`. Each assistant can have multiple prompt variants. Variants marked `current: true` appear on the dashboard; older versions show only in the detail view.

## Key Files

- `agents.yaml` - Registry of all coding assistants, their prompt file paths, and tool files
- `web/data/analysis.json` - Pipeline output consumed by the web UI. This is the contract between pipeline and UI - changes to its schema affect both sides.

## LLM Configuration

**Default provider:** Nebius hosting Qwen model
- `DEFAULT_LLM_MODEL` and `DEFAULT_LLM_BASE_URL` defined in `config.py`
- Override via `LLM_BASE_URL` environment variable for other providers
- API key always required in `.env` file
- Model can be specified via `--llm-model` CLI flag

## Conventions

- The web UI uses Pico CSS (classless) with minimal custom CSS
- Python 3.12+, `uv` for deps, `ruff` for lint/format, `pytest` for tests
