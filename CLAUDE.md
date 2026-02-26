# System Prompts Analyzer

## Terminology

- **Coding assistant**: The product (Claude Code, Cursor, Copilot, GitHub Copilot, Windsurf, etc.)
- **Prompt variant**: A specific system prompt for a coding assistant, possibly targeting a particular model (e.g., Copilot's GPT-4o prompt vs GPT-4.1 prompt)
- **Current**: The latest/active prompt variant(s) for a coding assistant
- Do NOT use "agent" to refer to coding assistants. In this codebase, "agent" appears in legacy field names (`agent_id`, `agent_name`) but conceptually these are coding assistants. Reserve "agent" for LLM agent concepts outside this project's domain.

## Project Structure

- `data/` - Raw system prompt files and tool definitions
- `src/spa/` - Python analysis pipeline
- `web/` - Static dashboard (vanilla JS, Pico CSS)
- `agents.yaml` - Registry of all coding assistants and their prompt files
- `web/data/analysis.json` - Pipeline output consumed by the web UI

## Commands

- `uv run spa` - Run the analysis pipeline
- `uv run pytest` - Run tests
- `uv run ruff check src tests` - Lint
- `uv run ruff format src tests` - Format

## Conventions

- See global CLAUDE.md for Python, git, and writing style conventions
- The web UI uses Pico CSS (classless) with minimal custom CSS
- `analysis.json` is the contract between pipeline and UI - changes affect both
