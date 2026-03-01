# CLI Output Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide clean, informative CLI output with smart error handling for the LLM analysis pipeline.

**Architecture:** Add custom exception types to categorize LLM errors (auth vs network), configure LiteLLM logging verbosity, replace progress logging with Rich Progress display, implement retry logic with exponential backoff for network errors and fail-fast for auth errors.

**Tech Stack:** Python 3.12, Rich (already installed), pytest for testing

---

## Task 1: Add Custom Exception Types

**Files:**
- Modify: `src/spa/llm/analyzer.py:1-10` (add imports and exception classes)
- Test: `tests/test_llm.py` (add new test section)

**Step 1: Write failing tests for custom exceptions**

```python
# Add to tests/test_llm.py
def test_authentication_error_inherits_from_llm_error():
    """AuthenticationError should inherit from LLMError."""
    from spa.llm.analyzer import AuthenticationError, LLMError

    error = AuthenticationError("Invalid API key")
    assert isinstance(error, LLMError)
    assert str(error) == "Invalid API key"


def test_network_error_inherits_from_llm_error():
    """NetworkError should inherit from LLMError."""
    from spa.llm.analyzer import NetworkError, LLMError

    error = NetworkError("Connection timeout")
    assert isinstance(error, LLMError)
    assert str(error) == "Connection timeout"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm.py::test_authentication_error_inherits_from_llm_error tests/test_llm.py::test_network_error_inherits_from_llm_error -v`

Expected: FAIL with "ImportError: cannot import name 'AuthenticationError'"

**Step 3: Add exception classes to analyzer.py**

Add after line 10 in `src/spa/llm/analyzer.py`:

```python
class LLMError(Exception):
    """Base exception for LLM analysis errors."""


class AuthenticationError(LLMError):
    """API key or authentication failed."""


class NetworkError(LLMError):
    """Network/connectivity issue."""
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm.py::test_authentication_error_inherits_from_llm_error tests/test_llm.py::test_network_error_inherits_from_llm_error -v`

Expected: PASS (2/2 tests)

**Step 5: Commit**

```bash
git add src/spa/llm/analyzer.py tests/test_llm.py
git commit -m "Add custom exception types for LLM errors"
```

---

## Task 2: Add Error Categorization in Analyzer

**Files:**
- Modify: `src/spa/llm/analyzer.py:120-145` (wrap litellm.completion calls)
- Test: `tests/test_llm.py` (add error categorization tests)

**Step 1: Write failing test for auth error detection**

```python
# Add to tests/test_llm.py
import pytest
from unittest.mock import patch, MagicMock


def test_analyze_assistant_raises_auth_error_on_invalid_key():
    """analyze_assistant should raise AuthenticationError on invalid API key."""
    from spa.llm.analyzer import analyze_assistant, AuthenticationError

    with patch("spa.llm.analyzer.litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("Invalid API key provided")

        with pytest.raises(AuthenticationError, match="API key invalid or missing"):
            analyze_assistant(
                raw_text="test prompt",
                tool_names=["Read", "Write"],
                assistant_name="Test Assistant",
                model="gpt-4",
            )


def test_analyze_assistant_raises_network_error_on_timeout():
    """analyze_assistant should raise NetworkError on connection timeout."""
    from spa.llm.analyzer import analyze_assistant, NetworkError

    with patch("spa.llm.analyzer.litellm.completion") as mock_completion:
        mock_completion.side_effect = Exception("Connection timeout after 30s")

        with pytest.raises(NetworkError, match="Network error"):
            analyze_assistant(
                raw_text="test prompt",
                tool_names=["Read", "Write"],
                assistant_name="Test Assistant",
                model="gpt-4",
            )
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_llm.py::test_analyze_assistant_raises_auth_error_on_invalid_key tests/test_llm.py::test_analyze_assistant_raises_network_error_on_timeout -v`

Expected: FAIL with different exception raised

**Step 3: Add error categorization in analyzer.py**

Modify the `analyze_assistant` function around line 143 (first attempt):

```python
# Replace the line:
#     response = litellm.completion(**kwargs)
# With:
try:
    response = litellm.completion(**kwargs)
except Exception as e:
    # Categorize the error
    error_str = str(e).lower()
    if "api key" in error_str or "unauthorized" in error_str or "authentication" in error_str:
        raise AuthenticationError(f"API key invalid or missing: {e}") from e
    elif "timeout" in error_str or "connection" in error_str or "network" in error_str:
        raise NetworkError(f"Network error: {e}") from e
    else:
        raise  # Re-raise unknown errors
```

Do the same for the retry attempt around line 167.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_llm.py::test_analyze_assistant_raises_auth_error_on_invalid_key tests/test_llm.py::test_analyze_assistant_raises_network_error_on_timeout -v`

Expected: PASS (2/2 tests)

**Step 5: Run all LLM tests to ensure no regression**

Run: `uv run pytest tests/test_llm.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/spa/llm/analyzer.py tests/test_llm.py
git commit -m "Add error categorization for auth and network errors"
```

---

## Task 3: Configure LiteLLM Logger Verbosity

**Files:**
- Modify: `src/spa/cli.py:110-115` (add LiteLLM logger configuration)
- Test: Manual testing (no automated test needed for logging configuration)

**Step 1: Add LiteLLM logger configuration**

Add after line 113 in `src/spa/cli.py` (after `logging.basicConfig(...)`):

```python
# Suppress LiteLLM's verbose logging unless --verbose
litellm_logger = logging.getLogger("LiteLLM")
if verbose:
    litellm_logger.setLevel(logging.DEBUG)
else:
    litellm_logger.setLevel(logging.ERROR)  # Only show errors
```

**Step 2: Test with verbose mode**

Run: `uv run spa --verbose --skip-llm`

Expected: Should see DEBUG level logs if LiteLLM emits any

**Step 3: Test with default mode**

Run: `uv run spa --skip-llm`

Expected: Should NOT see LiteLLM INFO logs

**Step 4: Commit**

```bash
git add src/spa/cli.py
git commit -m "Configure LiteLLM logger verbosity based on --verbose flag"
```

---

## Task 4: Add Rich Progress Display

**Files:**
- Modify: `src/spa/pipeline.py:1-20` (add Rich imports)
- Modify: `src/spa/pipeline.py:164-231` (replace logger.info with Rich Progress)
- Test: Manual testing (visual verification)

**Step 1: Add Rich imports**

Add to imports section at top of `src/spa/pipeline.py` (around line 10):

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
```

Also add time import for retry delays:

```python
import time
```

**Step 2: Replace LLM analysis loop with Rich Progress**

Replace the section from line 172 to line 222 in `src/spa/pipeline.py`:

```python
# Old code:
# logger.info("Running LLM analysis on %d prompts...", len(llm_inputs))
# for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
#     ...

# New code:
logger.info("Running LLM analysis on %d prompts...", len(llm_inputs))

# Determine if we should show progress (not quiet mode)
show_progress = True  # We'll check for quiet mode later

if show_progress:
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Analyzing prompts", total=len(llm_inputs))

        for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
            # Check cache: reuse previous LLM analysis if file is unchanged
            path_str = prompt_paths.get(prompt_key)
            if path_str and previous_prompts:
                current_hash = compute_file_hash(DATA_DIR / path_str)
                cached_hash = previous_file_hashes.get(path_str)
                if current_hash == cached_hash and prompt_key in previous_prompts:
                    cached_llm = previous_prompts[prompt_key].get("llm_analysis")
                    if cached_llm:
                        logger.debug("  %s: using cached LLM analysis", prompt_key)
                        analyses[prompt_key] = AssistantAnalysis(**cached_llm)
                        assistant_id, label = prompt_key.split("::", 1)
                        for entry in prompts_out:
                            if entry["assistant_id"] == assistant_id and entry["label"] == label:
                                entry["llm_analysis"] = cached_llm
                                break
                        progress.update(task, advance=1, description=f"✓ {prompt_key} (cached)")
                        continue

            try:
                analysis, usage = analyze_assistant(
                    raw_text=raw_text,
                    tool_names=tool_names,
                    assistant_name=assistant_name,
                    model=llm_model,
                )
                analyses[prompt_key] = analysis

                # Accumulate token usage
                total_tokens_used["prompt_tokens"] += usage["prompt_tokens"]
                total_tokens_used["completion_tokens"] += usage["completion_tokens"]
                total_tokens_used["total_tokens"] += usage["total_tokens"]

                logger.debug(
                    "  %s: %d tokens (in: %d, out: %d)",
                    prompt_key,
                    usage["total_tokens"],
                    usage["prompt_tokens"],
                    usage["completion_tokens"],
                )

                # Attach to the matching prompt entry
                assistant_id, label = prompt_key.split("::", 1)
                for entry in prompts_out:
                    if entry["assistant_id"] == assistant_id and entry["label"] == label:
                        entry["llm_analysis"] = analysis.model_dump()
                        break

                progress.update(task, advance=1, description=f"✓ {prompt_key}")
            except Exception as e:
                logger.exception("LLM analysis failed for %s", prompt_key)
                progress.update(task, advance=1, description=f"✗ {prompt_key} - {str(e)[:50]}")
else:
    # Quiet mode: no progress display (keep original loop logic)
    for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
        # ... (same logic as above but without progress updates)
        pass  # TODO: Will be filled in next step
```

**Step 3: Test progress display**

Run: `uv run spa --force`

Expected: See progress bar with ✓ marks and percentage

**Step 4: Test quiet mode preserves no-progress behavior**

Run: `uv run spa --force --quiet`

Expected: No progress bar shown

**Step 5: Commit**

```bash
git add src/spa/pipeline.py
git commit -m "Add Rich progress display for LLM analysis"
```

---

## Task 5: Add Retry Logic with Error Handling

**Files:**
- Modify: `src/spa/pipeline.py:190-220` (add retry logic in except blocks)
- Test: `tests/test_llm.py` (add retry tests)

**Step 1: Write test for authentication fail-fast**

```python
# Add to tests/test_llm.py
def test_pipeline_exits_on_authentication_error(tmp_path, monkeypatch):
    """Pipeline should exit immediately on authentication error."""
    from spa.llm.analyzer import AuthenticationError
    from spa.pipeline import run_pipeline
    import sys

    # Create minimal test environment
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    # Mock analyze_assistant to raise AuthenticationError
    with patch("spa.pipeline.analyze_assistant") as mock_analyze:
        mock_analyze.side_effect = AuthenticationError("Invalid API key")

        # Mock load_assistant_registry to return minimal data
        with patch("spa.pipeline.load_assistant_registry") as mock_registry:
            mock_registry.return_value = {
                "test-assistant": {
                    "name": "Test",
                    "prompts": [{"label": "v1", "path": "test.txt", "current": True}],
                    "tools": [],
                }
            }

            # Create a dummy prompt file
            test_file = tmp_path / "data" / "test.txt"
            test_file.parent.mkdir(parents=True)
            test_file.write_text("Test prompt")

            with patch("spa.pipeline.DATA_DIR", tmp_path / "data"):
                with pytest.raises(SystemExit) as exc_info:
                    run_pipeline(output_path=tmp_path / "output.json")

                assert exc_info.value.code == 1
                # Should only call analyze_assistant once (fail fast)
                assert mock_analyze.call_count == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_llm.py::test_pipeline_exits_on_authentication_error -v`

Expected: FAIL (SystemExit not raised, or multiple calls to analyze_assistant)

**Step 3: Add retry logic with error handling**

Modify the exception handling in `src/spa/pipeline.py` (within the progress loop):

```python
try:
    analysis, usage = analyze_assistant(
        raw_text=raw_text,
        tool_names=tool_names,
        assistant_name=assistant_name,
        model=llm_model,
    )
    # ... existing success code ...
except AuthenticationError as e:
    logger.error("Authentication failed: %s", e)
    logger.error("Stopping pipeline - check your LLM_API_KEY")
    sys.exit(1)  # Fail fast
except NetworkError as e:
    # Retry with exponential backoff (3 attempts)
    retry_success = False
    for attempt in range(3):
        logger.warning("Network error (attempt %d/3): %s", attempt + 1, e)
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
        try:
            analysis, usage = analyze_assistant(
                raw_text=raw_text,
                tool_names=tool_names,
                assistant_name=assistant_name,
                model=llm_model,
            )
            # ... same success code as above ...
            retry_success = True
            break  # Success
        except NetworkError as retry_e:
            e = retry_e
            if attempt == 2:  # Last attempt
                logger.error("Network error after 3 retries: %s", e)
                progress.update(task, advance=1, description=f"✗ {prompt_key} - network error")

    if retry_success:
        progress.update(task, advance=1, description=f"✓ {prompt_key}")
except Exception as e:
    logger.exception("LLM analysis failed for %s", prompt_key)
    progress.update(task, advance=1, description=f"✗ {prompt_key} - {str(e)[:50]}")
```

Don't forget to add the import at the top:

```python
from spa.llm.analyzer import AuthenticationError, NetworkError
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_llm.py::test_pipeline_exits_on_authentication_error -v`

Expected: PASS

**Step 5: Run all tests**

Run: `uv run pytest tests/test_llm.py -v`

Expected: All tests pass

**Step 6: Commit**

```bash
git add src/spa/pipeline.py tests/test_llm.py
git commit -m "Add retry logic for network errors and fail-fast for auth errors"
```

---

## Task 6: Update Verbose Mode Token Display

**Files:**
- Modify: `src/spa/pipeline.py:206-213` (change logger.info to logger.debug)
- Test: Manual testing

**Step 1: Change token logging to debug level**

The token logging is already at logger.debug level from Task 4. Verify this is correct.

**Step 2: Test verbose mode shows token details**

Run: `uv run spa --force --verbose`

Expected: Should see token count details like "14,250 tokens (in: 13,290, out: 960)"

**Step 3: Test default mode hides token details**

Run: `uv run spa --force`

Expected: Should NOT see token count details (only progress bar)

**Step 4: No commit needed** (already correct from Task 4)

---

## Task 7: Handle Quiet Mode in Progress Display

**Files:**
- Modify: `src/spa/pipeline.py:164-175` (detect quiet mode, conditionally show progress)
- Test: Manual testing

**Step 1: Check for quiet mode setting**

The `run_pipeline` function doesn't receive a `quiet` parameter. We need to check sys.argv or use logging level as a proxy.

Actually, looking at the code, there's no `quiet` parameter passed to `run_pipeline`. The quiet mode is handled in `cli.py` by not printing the final summary.

For progress display, we can check the logging level:

Modify around line 172 in `src/spa/pipeline.py`:

```python
# Determine if we should show progress (not in quiet mode)
show_progress = logger.getEffectiveLevel() < logging.WARNING

if show_progress and llm_inputs:
    with Progress(
        # ... progress code ...
```

**Step 2: Test quiet mode**

Run: `uv run spa --force --quiet`

Expected: No progress bar, minimal output

**Step 3: Test default mode**

Run: `uv run spa --force`

Expected: Progress bar shown

**Step 4: Commit**

```bash
git add src/spa/pipeline.py
git commit -m "Respect quiet mode in progress display"
```

---

## Task 8: Fill in Quiet Mode Loop Logic

**Files:**
- Modify: `src/spa/pipeline.py:230-240` (add quiet mode loop logic)

**Step 1: Copy analysis logic to quiet mode branch**

The `else:` branch for quiet mode (when `show_progress` is False) needs the same logic as the progress mode, just without progress updates:

```python
else:
    # Quiet mode: no progress display
    for prompt_key, (raw_text, tool_names, assistant_name) in llm_inputs.items():
        # Check cache
        path_str = prompt_paths.get(prompt_key)
        if path_str and previous_prompts:
            current_hash = compute_file_hash(DATA_DIR / path_str)
            cached_hash = previous_file_hashes.get(path_str)
            if current_hash == cached_hash and prompt_key in previous_prompts:
                cached_llm = previous_prompts[prompt_key].get("llm_analysis")
                if cached_llm:
                    logger.debug("  %s: using cached LLM analysis", prompt_key)
                    analyses[prompt_key] = AssistantAnalysis(**cached_llm)
                    assistant_id, label = prompt_key.split("::", 1)
                    for entry in prompts_out:
                        if entry["assistant_id"] == assistant_id and entry["label"] == label:
                            entry["llm_analysis"] = cached_llm
                            break
                    continue

        try:
            analysis, usage = analyze_assistant(
                raw_text=raw_text,
                tool_names=tool_names,
                assistant_name=assistant_name,
                model=llm_model,
            )
            analyses[prompt_key] = analysis
            total_tokens_used["prompt_tokens"] += usage["prompt_tokens"]
            total_tokens_used["completion_tokens"] += usage["completion_tokens"]
            total_tokens_used["total_tokens"] += usage["total_tokens"]

            logger.debug(
                "  %s: %d tokens (in: %d, out: %d)",
                prompt_key,
                usage["total_tokens"],
                usage["prompt_tokens"],
                usage["completion_tokens"],
            )

            assistant_id, label = prompt_key.split("::", 1)
            for entry in prompts_out:
                if entry["assistant_id"] == assistant_id and entry["label"] == label:
                    entry["llm_analysis"] = analysis.model_dump()
                    break
        except AuthenticationError as e:
            logger.error("Authentication failed: %s", e)
            logger.error("Stopping pipeline - check your LLM_API_KEY")
            sys.exit(1)
        except NetworkError as e:
            retry_success = False
            for attempt in range(3):
                logger.warning("Network error (attempt %d/3): %s", attempt + 1, e)
                time.sleep(2 ** attempt)
                try:
                    analysis, usage = analyze_assistant(
                        raw_text=raw_text,
                        tool_names=tool_names,
                        assistant_name=assistant_name,
                        model=llm_model,
                    )
                    analyses[prompt_key] = analysis
                    total_tokens_used["prompt_tokens"] += usage["prompt_tokens"]
                    total_tokens_used["completion_tokens"] += usage["completion_tokens"]
                    total_tokens_used["total_tokens"] += usage["total_tokens"]
                    logger.debug(
                        "  %s: %d tokens (in: %d, out: %d)",
                        prompt_key,
                        usage["total_tokens"],
                        usage["prompt_tokens"],
                        usage["completion_tokens"],
                    )
                    assistant_id, label = prompt_key.split("::", 1)
                    for entry in prompts_out:
                        if entry["assistant_id"] == assistant_id and entry["label"] == label:
                            entry["llm_analysis"] = analysis.model_dump()
                            break
                    retry_success = True
                    break
                except NetworkError as retry_e:
                    e = retry_e
                    if attempt == 2:
                        logger.error("Network error after 3 retries: %s", e)
        except Exception as e:
            logger.exception("LLM analysis failed for %s", prompt_key)
```

**Step 2: Run all tests**

Run: `uv run pytest tests/test_llm.py -v`

Expected: All tests pass

**Step 3: Test quiet mode end-to-end**

Run: `uv run spa --force --quiet`

Expected: Minimal output, analysis completes successfully

**Step 4: Commit**

```bash
git add src/spa/pipeline.py
git commit -m "Add quiet mode loop logic without progress display"
```

---

## Task 9: Manual Integration Testing

**Files:**
- None (testing only)

**Step 1: Test normal operation with valid API key**

Run: `uv run spa --force`

Expected:
- Clean progress bar with ✓ marks
- No LiteLLM INFO logs visible
- Final summary shown

**Step 2: Test verbose mode**

Run: `uv run spa --force --verbose`

Expected:
- Progress bar shown
- LiteLLM DEBUG logs visible
- Token counts shown for each prompt

**Step 3: Test quiet mode**

Run: `uv run spa --force --quiet`

Expected:
- No progress bar
- Minimal output
- Only errors/warnings shown

**Step 4: Test invalid API key (fail fast)**

Edit `.env` to set `LLM_API_KEY=invalid`

Run: `uv run spa --force`

Expected:
- First prompt fails with auth error
- Pipeline exits immediately
- Clear error message about checking LLM_API_KEY

Restore valid API key after testing.

**Step 5: Verify no regressions**

Run: `uv run pytest -v`

Expected: All tests pass

**Step 6: No commit** (testing only)

---

## Verification Checklist

- [ ] All new tests pass
- [ ] No regression in existing tests
- [ ] LiteLLM logs suppressed by default
- [ ] LiteLLM logs visible with `--verbose`
- [ ] Progress bar shows ✓/✗ status
- [ ] Token counts hidden by default
- [ ] Token counts shown with `--verbose`
- [ ] Quiet mode works (no progress bar)
- [ ] Invalid API key triggers immediate exit
- [ ] Network errors trigger retry with backoff
- [ ] Validation errors still retry (existing behavior)
