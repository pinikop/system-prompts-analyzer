# CLI Output Improvements Design

## Goal

Clean, informative CLI output with smart error handling for the LLM analysis pipeline.

## Problems

1. **Uninformative logging:** LiteLLM floods output with verbose INFO logs (`utils.py:3895`, `utils.py:1630`), making it hard to see actual progress
2. **Poor error handling:** If API key is invalid, the pipeline tries all prompts before failing, wasting time and showing repetitive tracebacks
3. **Too much detail by default:** Token counts for every prompt create noise; users just want to know if it's working

## Solution Overview

**Key changes:**
1. **Logging suppression:** Control LiteLLM verbosity via logging filters
2. **Progress display:** Use Rich Progress for live status updates
3. **Error categorization:** Distinguish auth errors (fail fast) vs network errors (retry)
4. **Verbosity modes:** Hide token details by default, show with `--verbose`

**Components affected:**
- `src/spa/cli.py` - Configure LiteLLM logger after basicConfig
- `src/spa/pipeline.py` - Replace logger.info calls with Rich Progress, add error categorization
- `src/spa/llm/analyzer.py` - Raise categorized exceptions, suppress internal logging

**No new dependencies:** Rich is already installed and used in the CLI.

## Design Details

### 1. Logging Control

**LiteLLM logger suppression:**

In `cli.py`, after `logging.basicConfig()`:

```python
# Suppress LiteLLM's verbose logging unless --verbose
litellm_logger = logging.getLogger("LiteLLM")
if verbose:
    litellm_logger.setLevel(logging.DEBUG)
else:
    litellm_logger.setLevel(logging.ERROR)  # Only show errors
```

**Our app logging strategy:**

- **Default mode:** Progress status only (✓/✗ per prompt)
- **Verbose mode:** Include token counts, cache hits, LiteLLM internals
- **Quiet mode:** No progress, only final summary

**Validation warnings:**

Format as: `⚠ vscode-copilot::Claude Sonnet 4 - retrying due to validation error`
- Show in default mode (actionable information)
- Include prompt name but not full traceback
- Brief enough to not overwhelm output

### 2. Progress Display

**Rich Progress integration:**

Replace the analysis loop in `pipeline.py` (lines 174-222):

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

if not quiet:
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Analyzing prompts", total=len(llm_inputs))
        for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
            # ... analysis logic ...
            progress.update(task, advance=1, description=f"✓ {prompt_key}")
else:
    # Quiet mode: no progress display, just process
    for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
        # ... analysis logic ...
```

**Output appearance:**

```
⠋ ✓ claude-code::v2.0 ████████░░░░░░░░ 50%
```

- On success: `✓ {prompt_key}`
- On failure: `✗ {prompt_key} - {brief_error}`

**Verbose mode additions:**

When `--verbose` is set, print token details after each prompt:
```
✓ claude-code::v2.0
  → 14,250 tokens (in: 13,290, out: 960)
```

### 3. Error Handling & Retry Logic

**Error categorization:**

In `analyzer.py`, add custom exception types:

```python
class LLMError(Exception):
    """Base exception for LLM analysis errors."""

class AuthenticationError(LLMError):
    """API key or authentication failed."""

class NetworkError(LLMError):
    """Network/connectivity issue."""
```

Wrap `litellm.completion()` to detect error types:

```python
try:
    response = litellm.completion(**kwargs)
except Exception as e:
    error_str = str(e).lower()
    if "api key" in error_str or "unauthorized" in error_str or "authentication" in error_str:
        raise AuthenticationError(f"API key invalid or missing: {e}") from e
    elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
        raise NetworkError(f"Network error: {e}") from e
    else:
        raise  # Re-raise unknown errors
```

**Pipeline error handling:**

In `pipeline.py`, handle categorized exceptions:

```python
try:
    analysis, usage = analyze_assistant(...)
except AuthenticationError as e:
    logger.error("Authentication failed: %s", e)
    logger.error("Stopping pipeline - check your LLM_API_KEY")
    sys.exit(1)  # Fail fast
except NetworkError as e:
    # Retry with exponential backoff (3 attempts)
    for attempt in range(3):
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
        try:
            analysis, usage = analyze_assistant(...)
            break  # Success
        except NetworkError:
            if attempt == 2:  # Last attempt
                logger.error("Network error after 3 retries: %s", e)
                continue  # Skip this prompt, continue pipeline
except Exception as e:
    logger.exception("LLM analysis failed for %s", prompt_key)
    # Continue processing other prompts
```

**Validation errors:** Already handled by retry mechanism in `analyzer.py` (lines 155-173), no change needed.

### 4. Testing

**Manual testing scenarios:**

1. **Normal operation:**
   - Run `uv run spa` with valid API key
   - Verify clean progress output with ✓/✗ status
   - Verify no LiteLLM internal logs visible

2. **Verbose mode:**
   - Run `uv run spa --verbose`
   - Verify LiteLLM logs appear
   - Verify token counts shown after each prompt

3. **Quiet mode:**
   - Run `uv run spa --quiet`
   - Verify only final summary shown

4. **Invalid API key:**
   - Set `LLM_API_KEY=invalid` in .env
   - Run `uv run spa`
   - Verify it fails fast on first prompt with clear auth error message
   - Verify pipeline doesn't continue trying all prompts

5. **Network issues (simulated):**
   - Test with `LLM_BASE_URL` pointing to non-existent server
   - Verify retry attempts occur
   - Verify backoff delays (1s, 2s, 4s)

**Automated tests:**

Add to `tests/test_llm.py`:
- Test `AuthenticationError` detection from error messages
- Test `NetworkError` detection from error messages
- Test retry logic with mocked network failures
- Test that validation errors still use existing retry mechanism

## Implementation Notes

**File changes:**
- `src/spa/cli.py` (~10 lines added)
- `src/spa/pipeline.py` (~40 lines modified, add Rich Progress)
- `src/spa/llm/analyzer.py` (~30 lines added for exceptions and categorization)
- `tests/test_llm.py` (~50 lines added for new tests)

**Edge cases:**
- If `--quiet` is set, no progress display (existing behavior preserved)
- If cache hit occurs, still show progress update
- If validation retry succeeds, show as success (not failure)
- Network retry delays should not block the progress bar (Rich handles this)

**Backward compatibility:**
- No breaking changes to CLI interface
- Existing `--verbose`, `--quiet` flags work as before
- Output format changes are cosmetic only
