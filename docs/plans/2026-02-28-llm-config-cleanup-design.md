# LLM Configuration Cleanup

**Date:** 2026-02-28
**Status:** Design approved, ready for implementation

## Problem

Current LLM configuration mixes secrets with configuration:

**Current state:**
- `DEFAULT_LLM_MODEL` is correctly in `config.py` ✓
- `LLM_BASE_URL` is in `.env.example` with a default value ✗
- This confuses what belongs in `.env` (secrets) vs code (configuration)

**Issues:**
1. `.env` files should contain only secrets (API keys, passwords)
2. Configuration values (base URLs, models) should be in code
3. Mixing them creates confusion about what to commit and what to keep private
4. Default values in `.env.example` aren't discoverable in code

## Solution

**Goal:** Separate secrets from configuration, allow environment variable overrides.

### Changes

**1. Add to `config.py`:**

```python
# LLM configuration (Nebius-hosted Qwen by default)
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-235B-A22B-Instruct-2507"  # existing
DEFAULT_LLM_BASE_URL = "https://api.studio.nebius.com/v1/"       # NEW
```

**Note:** The `openai/` prefix tells `litellm` to use OpenAI-compatible API format. The base URL determines where requests go (Nebius in this case).

**2. Update `analyzer.py`:**

```python
# Before (line 122):
base_url = os.environ.get("LLM_BASE_URL")

# After:
from spa.config import DEFAULT_LLM_BASE_URL
base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_LLM_BASE_URL
```

**3. Update `.env.example`:**

```bash
# Before:
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.studio.nebius.com/v1/

# After:
# LLM provider credentials
LLM_API_KEY=your-api-key-here
# LLM_BASE_URL is optional - set to override default Nebius endpoint
# Examples:
#   OpenAI: LLM_BASE_URL=https://api.openai.com/v1/
#   Anthropic: LLM_BASE_URL=https://api.anthropic.com/v1/
```

**4. Update documentation:**

Add to README.md:

```markdown
## LLM Configuration

**Default provider:** Nebius (hosting Qwen model)

**To use a different provider:**

1. Set `LLM_API_KEY` in `.env` with your provider's API key
2. *(Optional)* Set `LLM_BASE_URL` in `.env` to override the default Nebius endpoint:
   - OpenAI: `https://api.openai.com/v1/`
   - Anthropic: `https://api.anthropic.com/v1/`
   - Custom: Your provider's base URL
3. *(Optional)* Specify model via `--llm-model` flag (default: Qwen)

**Example - Using OpenAI:**

`.env`:
```bash
LLM_API_KEY=sk-proj-abc123...
LLM_BASE_URL=https://api.openai.com/v1/
```

CLI:
```bash
uv run spa --llm-model gpt-4o
```

**Example - Using default Nebius:**

`.env`:
```bash
LLM_API_KEY=your-nebius-key
```

CLI:
```bash
uv run spa  # Uses default Nebius + Qwen
```
```

Add to CLAUDE.md:

```markdown
## LLM Configuration

- Default provider: Nebius hosting Qwen model
- `DEFAULT_LLM_MODEL` and `DEFAULT_LLM_BASE_URL` in `config.py`
- Override via `LLM_BASE_URL` environment variable for other providers
- API key always required in `.env`
```

## Migration

**Backward compatible - no breaking changes.**

**For existing users:**

1. **If `.env` has `LLM_BASE_URL=https://api.studio.nebius.com/v1/`:**
   - Can remove it (now the default)
   - Or keep it (still works, just redundant)

2. **If `.env` has custom `LLM_BASE_URL`:**
   - Keep it (works as override)
   - No changes needed

3. **If no `.env` file yet:**
   - Copy `.env.example`
   - Set `LLM_API_KEY`
   - Optionally set `LLM_BASE_URL` for non-Nebius providers

## Testing

**Unit tests:**

```python
# tests/test_llm.py
def test_base_url_uses_default():
    """Uses DEFAULT_LLM_BASE_URL when env var not set."""
    from spa.config import DEFAULT_LLM_BASE_URL

    with patch.dict(os.environ, {}, clear=True):
        with patch("litellm.completion") as mock:
            mock.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                usage=None
            )
            analyze_assistant("prompt", [], "TestBot", "test-model")

            assert mock.call_args[1]["api_base"] == DEFAULT_LLM_BASE_URL


def test_base_url_env_override():
    """LLM_BASE_URL env var overrides default."""
    custom_url = "https://custom.api.com/v1/"

    with patch.dict(os.environ, {"LLM_BASE_URL": custom_url}):
        with patch("litellm.completion") as mock:
            mock.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                usage=None
            )
            analyze_assistant("prompt", [], "TestBot", "test-model")

            assert mock.call_args[1]["api_base"] == custom_url
```

**Manual testing:**

1. Remove `LLM_BASE_URL` from `.env`, run `uv run spa` → should use Nebius
2. Set `LLM_BASE_URL=https://api.openai.com/v1/` in `.env`, run pipeline → should use OpenAI
3. Verify `--llm-model` flag still works with both default and custom base URLs

## Benefits

1. **Clear separation:** Secrets in `.env`, configuration in `config.py`
2. **Discoverability:** Default base URL visible in code, not hidden in `.env.example`
3. **Flexibility:** Users can still override for any provider
4. **Consistency:** Matches existing pattern with `DEFAULT_LLM_MODEL`
5. **Documentation:** Clear docs on how to use different providers
6. **Backward compatible:** No breaking changes for existing users
