# LLM Configuration Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move LLM_BASE_URL from .env to config.py for clean separation of secrets and configuration.

**Architecture:** Add DEFAULT_LLM_BASE_URL constant to config.py, update analyzer.py to use it as fallback when environment variable not set.

**Tech Stack:** Python 3.12, existing test framework (pytest)

---

## Task 1: Add DEFAULT_LLM_BASE_URL to config.py

**Files:**
- Modify: `src/spa/config.py`

**Step 1: Add constant to config.py**

```python
# src/spa/config.py (add after DEFAULT_LLM_MODEL, line 26)
DEFAULT_LLM_MODEL = "openai/Qwen/Qwen3-235B-A22B-Instruct-2507"
DEFAULT_LLM_BASE_URL = "https://api.studio.nebius.com/v1/"  # NEW
```

**Step 2: Verify no syntax errors**

```bash
uv run python -c "from spa.config import DEFAULT_LLM_BASE_URL; print(DEFAULT_LLM_BASE_URL)"
```
Expected: `https://api.studio.nebius.com/v1/`

**Step 3: Commit**

```bash
git add src/spa/config.py
git commit -m "Add DEFAULT_LLM_BASE_URL constant to config"
```

---

## Task 2: Update analyzer.py to use default

**Files:**
- Modify: `src/spa/llm/analyzer.py:122`
- Test: `tests/test_llm.py`

**Step 1: Write failing test for default base URL**

```python
# tests/test_llm.py (add after TestAnalyzeAssistantIntegration class)
import os
from unittest.mock import patch


class TestBaseUrlConfiguration:
    def test_uses_default_when_env_not_set(self) -> None:
        """Uses DEFAULT_LLM_BASE_URL when env var not set."""
        from spa.config import DEFAULT_LLM_BASE_URL

        # Clear environment
        with patch.dict(os.environ, {}, clear=True):
            with patch("litellm.completion") as mock_completion:
                mock_completion.return_value = MagicMock(
                    choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                    usage=None
                )

                from spa.llm.analyzer import analyze_assistant
                analyze_assistant(
                    raw_text="test",
                    tool_names=[],
                    assistant_name="TestBot",
                    model="test-model",
                )

                # Verify api_base was set to default
                call_kwargs = mock_completion.call_args[1]
                assert call_kwargs["api_base"] == DEFAULT_LLM_BASE_URL
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_llm.py::TestBaseUrlConfiguration::test_uses_default_when_env_not_set -v
```
Expected: FAIL (api_base is None or not set)

**Step 3: Update analyzer.py to import and use default**

```python
# src/spa/llm/analyzer.py
# Add to imports at top (line 7)
from spa.config import DEFAULT_LLM_BASE_URL

# Update analyze_assistant function (around line 122)
# Before:
    base_url = os.environ.get("LLM_BASE_URL")

# After:
    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_LLM_BASE_URL
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_llm.py::TestBaseUrlConfiguration::test_uses_default_when_env_not_set -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/llm/analyzer.py tests/test_llm.py
git commit -m "Use DEFAULT_LLM_BASE_URL as fallback in analyzer"
```

---

## Task 3: Test environment variable override

**Files:**
- Test: `tests/test_llm.py`

**Step 1: Write failing test for env override**

```python
# tests/test_llm.py (add to TestBaseUrlConfiguration class)
def test_env_var_overrides_default(self) -> None:
    """LLM_BASE_URL env var overrides DEFAULT_LLM_BASE_URL."""
    custom_url = "https://api.openai.com/v1/"

    with patch.dict(os.environ, {"LLM_BASE_URL": custom_url}):
        with patch("litellm.completion") as mock_completion:
            mock_completion.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps(VALID_ANALYSIS)))],
                usage=None
            )

            from spa.llm.analyzer import analyze_assistant
            analyze_assistant(
                raw_text="test",
                tool_names=[],
                assistant_name="TestBot",
                model="test-model",
            )

            # Verify api_base was set to custom URL
            call_kwargs = mock_completion.call_args[1]
            assert call_kwargs["api_base"] == custom_url
```

**Step 2: Run test to verify it passes**

```bash
uv run pytest tests/test_llm.py::TestBaseUrlConfiguration::test_env_var_overrides_default -v
```
Expected: PASS (implementation from Task 2 should already handle this)

**Step 3: Run all LLM tests to ensure no regressions**

```bash
uv run pytest tests/test_llm.py -v
```
Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_llm.py
git commit -m "Add test for LLM_BASE_URL env var override"
```

---

## Task 4: Update .env.example

**Files:**
- Modify: `.env.example`

**Step 1: Update .env.example with comments**

```bash
# .env.example (replace entire content)
# LLM provider credentials for thematic analysis
LLM_API_KEY=your-api-key-here

# Optional: Override default LLM base URL (default is Nebius)
# Uncomment and set to use a different provider:
# LLM_BASE_URL=https://api.openai.com/v1/          # OpenAI
# LLM_BASE_URL=https://api.anthropic.com/v1/       # Anthropic
# LLM_BASE_URL=https://your-custom-endpoint.com/   # Custom
```

**Step 2: Verify file is valid**

```bash
cat .env.example
```
Expected: Shows updated content with helpful comments

**Step 3: Commit**

```bash
git add .env.example
git commit -m "Update .env.example with optional LLM_BASE_URL override"
```

---

## Task 5: Update README.md

**Files:**
- Modify: `README.md`

**Step 1: Add LLM configuration section**

Find the setup section in README.md and add after installation instructions:

```markdown
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
- OpenAI - Set `LLM_BASE_URL=https://api.openai.com/v1/`
- Anthropic - Set `LLM_BASE_URL=https://api.anthropic.com/v1/`
- Any OpenAI-compatible API - Set `LLM_BASE_URL` to your endpoint
```

**Step 2: Verify markdown rendering**

```bash
# Preview README locally or check formatting
head -50 README.md
```
Expected: Section appears correctly formatted

**Step 3: Commit**

```bash
git add README.md
git commit -m "Add LLM configuration section to README"
```

---

## Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add LLM config note to architecture section**

Find the "Architecture" section in CLAUDE.md and add:

```markdown
## LLM Configuration

**Default provider:** Nebius hosting Qwen model
- `DEFAULT_LLM_MODEL` and `DEFAULT_LLM_BASE_URL` defined in `config.py`
- Override via `LLM_BASE_URL` environment variable for other providers
- API key always required in `.env` file
- Model can be specified via `--llm-model` CLI flag
```

**Step 2: Verify file is valid**

```bash
grep -A 5 "LLM Configuration" CLAUDE.md
```
Expected: Shows new section

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Document LLM configuration in CLAUDE.md"
```

---

## Task 7: Final verification

**Step 1: Run full test suite**

```bash
uv run pytest -v
```
Expected: All tests PASS (should be 90 total: 88 existing + 2 new)

**Step 2: Test with ruff**

```bash
uv run ruff check src tests
uv run ruff format --check src tests
```
Expected: No issues

**Step 3: Manual smoke test (if API key available)**

```bash
# Remove LLM_BASE_URL from .env if present
uv run spa --skip-llm  # Should work fine
```
Expected: Pipeline runs successfully

**Step 4: Verify git status**

```bash
git status
git log --oneline -7
```
Expected:
- Clean working directory
- 7 commits for this feature (1 per task)

---

## Summary

**Changes made:**
1. Added `DEFAULT_LLM_BASE_URL` to `config.py`
2. Updated `analyzer.py` to use default with env override
3. Added 2 tests for default and override behavior
4. Updated `.env.example` with helpful comments
5. Documented LLM config in README and CLAUDE.md

**Backward compatibility:**
- Existing `.env` files with `LLM_BASE_URL` still work (override)
- Existing `.env` files without `LLM_BASE_URL` now use default (no change in behavior)
- No breaking changes

**Benefits:**
- Secrets (API keys) separated from config (base URLs)
- Default configuration visible in code
- Easy to override for different providers
- Clear documentation for users
