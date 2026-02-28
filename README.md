# System Prompts Analyzer

Analyzes coding assistant system prompts with rule-based metrics and optional LLM-powered thematic analysis.

## Setup

```bash
uv sync --extra llm   # include LLM analysis support
cp .env.example .env  # add your API key
uv run spa            # run the pipeline
```

## LLM Configuration

The analyzer uses **Nebius-hosted Qwen** by default for LLM analysis.

**Quick start (Nebius):**
```bash
# .env
LLM_API_KEY=your-nebius-api-key
```

**Using a different provider:**

Set `LLM_BASE_URL` in `.env` to override the default:

```bash
# .env - OpenAI example
LLM_API_KEY=sk-proj-abc123...
LLM_BASE_URL=https://api.openai.com/v1/
```

Then specify the model:
```bash
uv run spa --llm-model gpt-4o
```

**Supported providers:**
- Nebius (default) - `LLM_API_KEY` only
- OpenAI - set `LLM_BASE_URL=https://api.openai.com/v1/`
- Anthropic - set `LLM_BASE_URL=https://api.anthropic.com/v1/`
- Any OpenAI-compatible API - set `LLM_BASE_URL` to your endpoint

## Skip LLM analysis

```bash
uv run spa --skip-llm
```
