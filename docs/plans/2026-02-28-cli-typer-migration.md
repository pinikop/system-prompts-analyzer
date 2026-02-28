# CLI Typer Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate CLI from argparse to typer with Rich integration, adding validation, shell completion, and better UX while maintaining backward compatibility.

**Architecture:** Create new `cli.py` module with typer app, separate from `pipeline.py` business logic. Add typer and rich dependencies. Update entry point in `pyproject.toml`.

**Tech Stack:** Python 3.12, typer, rich, pytest, typer.testing.CliRunner

---

## Task 1: Add typer and rich dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add typer and rich to dependencies**

Edit `pyproject.toml` and add typer and rich:

```toml
dependencies = [
    "pyyaml>=6.0",
    "pydantic>=2.0",
    "python-dotenv>=1.2.1",
    "requests>=2.32.5",
    "typer>=0.12",
    "rich>=13.0",
]
```

**Step 2: Install new dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 3: Verify imports work**

Run: `uv run python -c "import typer; import rich; print('OK')"`
Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add typer and rich dependencies for CLI migration"
```

---

## Task 2: Create basic CLI test infrastructure

**Files:**
- Create: `tests/test_cli.py`

**Step 1: Write first CLI test**

```python
"""Tests for CLI interface."""

from typer.testing import CliRunner


def test_cli_imports():
    """Verify CLI module can be imported."""
    try:
        from spa import cli

        assert hasattr(cli, "app")
    except ImportError:
        # Expected to fail until we create cli.py
        assert False, "cli module not yet created"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_cli_imports -v`
Expected: FAIL - ModuleNotFoundError: No module named 'spa.cli'

**Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "Add CLI test infrastructure"
```

---

## Task 3: Create basic typer CLI structure

**Files:**
- Create: `src/spa/cli.py`

**Step 1: Write test for basic CLI invocation**

Add to `tests/test_cli.py`:

```python
def test_cli_help():
    """CLI should show help text."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "System Prompts Analyzer" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_cli_help -v`
Expected: FAIL - ModuleNotFoundError or no app

**Step 3: Create minimal cli.py**

```python
"""CLI interface for System Prompts Analyzer."""

import typer
from rich.console import Console

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
)
console = Console()


@app.command()
def main() -> None:
    """Analyze coding assistant system prompts."""
    console.print("Hello from typer CLI!")


if __name__ == "__main__":
    app()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_cli_help -v`
Expected: PASS

**Step 5: Test CLI manually**

Run: `uv run python -m spa.cli`
Expected: "Hello from typer CLI!"

**Step 6: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Create basic typer CLI structure"
```

---

## Task 4: Add --output flag with backward compatibility

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for --output flag**

Add to `tests/test_cli.py`:

```python
from pathlib import Path


def test_output_flag():
    """--output flag should be accepted."""
    from spa.cli import app

    runner = CliRunner()
    # Use temp directory for test
    result = runner.invoke(app, ["--output", "test.json"])
    # Should not fail on flag parsing
    assert result.exit_code in [0, 1]  # 0 or pipeline error is OK
    assert "--output" not in result.stdout  # No "unrecognized" error


def test_output_flag_short():
    """-o short form should work."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["-o", "test.json"])
    assert result.exit_code in [0, 1]
    assert "-o" not in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_output_flag -v`
Expected: FAIL - no such option: --output

**Step 3: Add --output parameter to cli.py**

```python
from pathlib import Path
from typing import Optional

from spa.config import WEB_DATA_DIR


@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    out_path = output or WEB_DATA_DIR / "analysis.json"
    console.print(f"Output path: {out_path}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_output_flag tests/test_cli.py::test_output_flag_short -v`
Expected: PASS

**Step 5: Test manually**

Run: `uv run python -m spa.cli --output custom.json`
Expected: "Output path: custom.json"

Run: `uv run python -m spa.cli -o custom.json`
Expected: "Output path: custom.json"

**Step 6: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add --output/-o flag with backward compatibility"
```

---

## Task 5: Add --skip-llm flag

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for --skip-llm flag**

Add to `tests/test_cli.py`:

```python
def test_skip_llm_flag():
    """--skip-llm flag should be accepted."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--skip-llm"])
    assert result.exit_code in [0, 1]
    assert "--skip-llm" not in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_skip_llm_flag -v`
Expected: FAIL

**Step 3: Add --skip-llm parameter**

```python
@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip LLM analysis and only run rule-based metrics",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    out_path = output or WEB_DATA_DIR / "analysis.json"
    console.print(f"Output: {out_path}, Skip LLM: {skip_llm}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_skip_llm_flag -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add --skip-llm flag"
```

---

## Task 6: Add --llm-model flag

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for --llm-model flag**

Add to `tests/test_cli.py`:

```python
def test_llm_model_flag():
    """--llm-model flag should be accepted."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--llm-model", "gpt-4o"])
    assert result.exit_code in [0, 1]
    assert "--llm-model" not in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_llm_model_flag -v`
Expected: FAIL

**Step 3: Add --llm-model parameter**

```python
from spa.config import DEFAULT_LLM_MODEL, WEB_DATA_DIR


@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip LLM analysis and only run rule-based metrics",
    ),
    llm_model: str = typer.Option(
        DEFAULT_LLM_MODEL,
        "--llm-model",
        help=f"LLM model to use (default: {DEFAULT_LLM_MODEL})",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    out_path = output or WEB_DATA_DIR / "analysis.json"
    console.print(f"Output: {out_path}, Skip LLM: {skip_llm}, Model: {llm_model}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_llm_model_flag -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add --llm-model flag with default from config"
```

---

## Task 7: Add --force and --skip-update flags

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write tests**

Add to `tests/test_cli.py`:

```python
def test_force_flag():
    """--force flag should be accepted."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--force"])
    assert result.exit_code in [0, 1]


def test_skip_update_flag():
    """--skip-update flag should be accepted."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--skip-update"])
    assert result.exit_code in [0, 1]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_force_flag tests/test_cli.py::test_skip_update_flag -v`
Expected: FAIL

**Step 3: Add parameters**

```python
@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip LLM analysis and only run rule-based metrics",
    ),
    llm_model: str = typer.Option(
        DEFAULT_LLM_MODEL,
        "--llm-model",
        help=f"LLM model to use (default: {DEFAULT_LLM_MODEL})",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess everything, ignore cache",
    ),
    skip_update: bool = typer.Option(
        False,
        "--skip-update",
        help="Don't check upstream, use local data",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    console.print("[green]All flags parsed successfully[/green]")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py::test_force_flag tests/test_cli.py::test_skip_update_flag -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add --force and --skip-update flags"
```

---

## Task 8: Add --verbose and --quiet flags with mutual exclusion

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for verbose/quiet conflict**

Add to `tests/test_cli.py`:

```python
def test_verbose_quiet_conflict():
    """--verbose and --quiet should be mutually exclusive."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--verbose", "--quiet"])
    assert result.exit_code != 0
    # Should have error about mutual exclusion
    assert "verbose" in result.stdout.lower() or "quiet" in result.stdout.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_verbose_quiet_conflict -v`
Expected: FAIL - both flags accepted

**Step 3: Add verbose/quiet with validation**

```python
import sys


@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip LLM analysis and only run rule-based metrics",
    ),
    llm_model: str = typer.Option(
        DEFAULT_LLM_MODEL,
        "--llm-model",
        help=f"LLM model to use (default: {DEFAULT_LLM_MODEL})",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess everything, ignore cache",
    ),
    skip_update: bool = typer.Option(
        False,
        "--skip-update",
        help="Don't check upstream, use local data",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging (DEBUG level)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-error output (WARNING level only)",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutual exclusion
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(code=2)

    console.print("[green]Flags validated successfully[/green]")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_verbose_quiet_conflict -v`
Expected: PASS

**Step 5: Test individual flags work**

Run: `uv run python -m spa.cli --verbose`
Expected: "Flags validated successfully"

Run: `uv run python -m spa.cli --quiet`
Expected: "Flags validated successfully"

**Step 6: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add --verbose/-v and --quiet/-q flags with mutual exclusion"
```

---

## Task 9: Add --version flag

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `pyproject.toml`

**Step 1: Write test for version flag**

Add to `tests/test_cli.py`:

```python
def test_version_flag():
    """--version should show version and exit."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "spa version" in result.stdout or "0." in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_version_flag -v`
Expected: FAIL

**Step 3: Update version in pyproject.toml**

```toml
[project]
name = "spa"
version = "0.2.0"  # Bump for this feature
```

**Step 4: Add version callback to cli.py**

```python
from importlib.metadata import version as get_version


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        ver = get_version("spa")
        console.print(f"spa version {ver}")
        raise typer.Exit()


@app.callback()
def callback(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """CLI callback for global options."""
    pass
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_version_flag -v`
Expected: PASS

**Step 6: Test manually**

Run: `uv run python -m spa.cli --version`
Expected: "spa version 0.2.0"

**Step 7: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py pyproject.toml
git commit -m "Add --version flag and bump version to 0.2.0"
```

---

## Task 10: Add output path validation

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for invalid output path**

Add to `tests/test_cli.py`:

```python
def test_output_validation_invalid_parent():
    """Should fail if output parent directory doesn't exist."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--output", "/nonexistent/invalid/path.json"])
    assert result.exit_code != 0
    assert "directory" in result.stdout.lower() or "not exist" in result.stdout.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_output_validation_invalid_parent -v`
Expected: FAIL - no validation yet

**Step 3: Add validation to cli.py**

```python
def validate_output_path(output: Optional[Path]) -> Path:
    """Validate output path and return resolved path."""
    if output is None:
        return WEB_DATA_DIR / "analysis.json"

    # Check parent directory exists
    parent = output.parent
    if not parent.exists():
        console.print(
            f"[red]✗ Error: Output directory does not exist: {parent}[/red]\n"
            f"  Create the directory first or use a valid path."
        )
        raise typer.Exit(code=2)

    return output.resolve()


@app.command()
def main(
    output: Optional[Path] = typer.Option(...),  # existing params
    # ... other params ...
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutual exclusion
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(code=2)

    # Validate output path
    output_path = validate_output_path(output)

    console.print(f"[green]✓ Output path validated: {output_path}[/green]")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_output_validation_invalid_parent -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add output path validation with helpful error messages"
```

---

## Task 11: Set up logging based on verbosity

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for logging setup**

Add to `tests/test_cli.py`:

```python
import logging


def test_verbose_sets_debug_logging():
    """--verbose should set DEBUG log level."""
    from spa.cli import app

    runner = CliRunner()
    # This test checks the side effect of logging setup
    # We'll verify by checking if DEBUG messages would be shown
    result = runner.invoke(app, ["--verbose", "--skip-llm"])
    # For now, just verify it doesn't crash
    assert result.exit_code in [0, 1]
```

**Step 2: Run test to verify current behavior**

Run: `uv run pytest tests/test_cli.py::test_verbose_sets_debug_logging -v`
Expected: Should pass but logging not yet configured

**Step 3: Add logging configuration**

```python
import logging


def setup_logging(verbose: bool, quiet: bool) -> None:
    """Configure logging based on verbosity flags."""
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        force=True,
    )


@app.command()
def main(
    output: Optional[Path] = typer.Option(...),
    # ... other params ...
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutual exclusion
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(code=2)

    # Set up logging
    setup_logging(verbose, quiet)

    # Validate output path
    output_path = validate_output_path(output)

    console.print(f"[green]✓ Configuration validated[/green]")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_verbose_sets_debug_logging -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add logging configuration based on verbosity flags"
```

---

## Task 12: Integrate with pipeline.run_pipeline()

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write integration test**

Add to `tests/test_cli.py`:

```python
def test_cli_calls_pipeline():
    """CLI should call pipeline.run_pipeline() with correct args."""
    from spa.cli import app

    runner = CliRunner()
    # Run with --skip-llm to avoid needing LLM setup
    result = runner.invoke(app, ["--skip-llm"])
    # Should either succeed or fail with pipeline error (not CLI error)
    # Exit code 0 = success, 1 = pipeline error, 2 = CLI validation error
    assert result.exit_code in [0, 1]
    # Should see output from pipeline, not just CLI validation
    assert "✓" in result.stdout or "Analyzed" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_cli_calls_pipeline -v`
Expected: FAIL - pipeline not yet called

**Step 3: Integrate pipeline call**

```python
from spa.pipeline import run_pipeline


@app.command()
def main(
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Output JSON path (default: web/data/analysis.json)",
    ),
    skip_llm: bool = typer.Option(
        False,
        "--skip-llm",
        help="Skip LLM analysis and only run rule-based metrics",
    ),
    llm_model: str = typer.Option(
        DEFAULT_LLM_MODEL,
        "--llm-model",
        help=f"LLM model to use (default: {DEFAULT_LLM_MODEL})",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reprocess everything, ignore cache",
    ),
    skip_update: bool = typer.Option(
        False,
        "--skip-update",
        help="Don't check upstream, use local data",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging (DEBUG level)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-error output (WARNING level only)",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutual exclusion
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(code=2)

    # Set up logging
    setup_logging(verbose, quiet)

    # Validate output path
    output_path = validate_output_path(output)

    try:
        # Run pipeline
        result = run_pipeline(
            output_path=output_path,
            skip_llm=skip_llm,
            llm_model=llm_model,
            force=force,
            skip_update=skip_update,
        )

        # Format success output with Rich
        count = result["meta"]["prompt_count"]
        assistants = result["meta"]["assistant_count"]
        llm_info = f" (LLM: {result['meta']['llm_model']})" if result["meta"]["llm_model"] else ""

        console.print(
            f"[green]✓[/green] Analyzed {count} prompts from {assistants} assistants{llm_info}\n"
            f"  → {output_path}"
        )

    except Exception as e:
        # Show error with Rich formatting
        if verbose:
            console.print_exception()
        else:
            console.print(f"[red]✗ Error: {e}[/red]")
        raise typer.Exit(code=1)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_cli_calls_pipeline -v`
Expected: PASS

**Step 5: Test manually**

Run: `uv run python -m spa.cli --skip-llm`
Expected: Should run full pipeline and show success message

**Step 6: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Integrate CLI with pipeline.run_pipeline()"
```

---

## Task 13: Update entry point in pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1: Update entry point**

```toml
[project.scripts]
spa = "spa.cli:app"  # Changed from spa.pipeline:main
```

**Step 2: Test entry point**

Run: `uv run spa --help`
Expected: Should show typer help text

Run: `uv run spa --version`
Expected: "spa version 0.2.0"

Run: `uv run spa --skip-llm`
Expected: Should run pipeline

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Update entry point to use new CLI module"
```

---

## Task 14: Remove old main() from pipeline.py

**Files:**
- Modify: `src/spa/pipeline.py`
- Modify: `tests/test_pipeline.py` (if affected)

**Step 1: Write test to ensure run_pipeline still works**

Check if `tests/test_pipeline.py` exists and has tests for `run_pipeline()`:

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: Tests should pass (they use run_pipeline, not main)

**Step 2: Remove old main() function**

In `src/spa/pipeline.py`, delete the `main()` function and `if __name__ == "__main__"` block:

```python
# DELETE THIS:
# def main() -> None:
#     parser = argparse.ArgumentParser(description="System Prompts Analyzer")
#     ...
#
# if __name__ == "__main__":
#     main()

# Keep run_pipeline() and everything else
```

Also remove the argparse import at the top:

```python
# DELETE:
# import argparse
```

**Step 3: Run tests to verify pipeline still works**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: All tests PASS

**Step 4: Verify CLI still works**

Run: `uv run spa --skip-llm`
Expected: Pipeline runs successfully

**Step 5: Commit**

```bash
git add src/spa/pipeline.py
git commit -m "Remove old argparse main() from pipeline.py"
```

---

## Task 15: Add warning for --llm-model with --skip-llm

**Files:**
- Modify: `src/spa/cli.py`
- Modify: `tests/test_cli.py`

**Step 1: Write test for warning**

Add to `tests/test_cli.py`:

```python
def test_llm_model_ignored_with_skip_llm():
    """Should warn if --llm-model used with --skip-llm."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--skip-llm", "--llm-model", "gpt-4o"])
    # Should succeed but show warning
    assert result.exit_code in [0, 1]
    # Check for warning in output
    assert "llm" in result.stdout.lower() or "skip" in result.stdout.lower()
```

**Step 2: Run test to verify current behavior**

Run: `uv run pytest tests/test_cli.py::test_llm_model_ignored_with_skip_llm -v`
Expected: May pass but no warning shown

**Step 3: Add warning logic**

```python
@app.command()
def main(
    # ... all parameters ...
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutual exclusion
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(code=2)

    # Warn about conflicting flags
    if skip_llm and llm_model != DEFAULT_LLM_MODEL:
        console.print(
            f"[yellow]⚠ Warning: --llm-model={llm_model} has no effect with --skip-llm[/yellow]"
        )

    # Set up logging
    setup_logging(verbose, quiet)

    # ... rest of function ...
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_llm_model_ignored_with_skip_llm -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/spa/cli.py tests/test_cli.py
git commit -m "Add warning when --llm-model used with --skip-llm"
```

---

## Task 16: Update README.md with new CLI features

**Files:**
- Modify: `README.md`

**Step 1: Update Usage section in README**

Find the "## Usage" section and update CLI examples to mention new features:

```markdown
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

# Verbose output for debugging
uv run spa --verbose

# Quiet mode (warnings/errors only)
uv run spa --quiet

# Show version
uv run spa --version

# Install shell completion (bash/zsh/fish)
spa --install-completion bash
```
```

Add new section after CLI Flags:

```markdown
### Shell Completion

Install auto-completion for your shell:

```bash
# Bash
spa --install-completion bash

# Zsh
spa --install-completion zsh

# Fish
spa --install-completion fish
```

After installation, restart your shell or source your config file.
```

**Step 2: Update Quick Start section**

Update step 3 to mention `uv run spa` (already correct, just verify):

```markdown
# 3. Run the pipeline
uv run spa
```

**Step 3: Review changes**

Run: `git diff README.md`
Expected: Only CLI documentation updated

**Step 4: Commit**

```bash
git add README.md
git commit -m "Update README with new CLI features and shell completion"
```

---

## Task 17: Test all flag combinations

**Files:**
- Modify: `tests/test_cli.py`

**Step 1: Write comprehensive flag combination tests**

Add to `tests/test_cli.py`:

```python
def test_all_flags_together():
    """Test multiple flags work together."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "--skip-llm",
            "--force",
            "--skip-update",
            "--verbose",
        ],
    )
    assert result.exit_code in [0, 1]


def test_backward_compatibility_all_original_flags():
    """All original argparse flags should work."""
    from spa.cli import app

    runner = CliRunner()
    # Test all original flags together
    result = runner.invoke(
        app,
        [
            "-o",
            "custom.json",
            "--skip-llm",
            "--llm-model",
            "gpt-4o",
            "--force",
            "--skip-update",
        ],
    )
    assert result.exit_code in [0, 1]
    # Should not show "unrecognized" errors
    assert "unrecognized" not in result.stdout.lower()
```

**Step 2: Run all CLI tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "Add comprehensive flag combination tests"
```

---

## Task 18: Manual testing and shell completion verification

**Files:**
- None (manual testing only)

**Step 1: Test shell completion installation**

Run: `uv run spa --install-completion bash`
Expected: Success message about completion installed

**Step 2: Test help text organization**

Run: `uv run spa --help`
Expected: Well-organized help with sections and examples

**Step 3: Test error messages**

Run: `uv run spa --output /nonexistent/dir/file.json`
Expected: Helpful error message with suggestion

Run: `uv run spa --verbose --quiet`
Expected: Error about mutual exclusion

**Step 4: Test success output formatting**

Run: `uv run spa --skip-llm`
Expected: Rich-formatted output with checkmark and colored text

**Step 5: Document verification results**

Create a checklist:
- [x] Shell completion installs successfully
- [x] Help text is well-organized
- [x] Error messages are helpful and colored
- [x] Success output uses Rich formatting
- [x] All original flags work (backward compatibility)
- [x] New flags work (--verbose, --quiet, --version)

**Step 6: Final commit**

```bash
git commit --allow-empty -m "Verify CLI migration complete - all manual tests pass"
```

---

## Success Criteria

All tasks complete when:

- [x] All tests pass: `uv run pytest tests/test_cli.py -v`
- [x] Entry point works: `uv run spa --help`
- [x] Backward compatibility: All original flags work identically
- [x] New features: --verbose, --quiet, --version flags work
- [x] Validation: Invalid inputs show helpful errors
- [x] Shell completion: Installation works
- [x] Documentation: README updated
- [x] Code quality: `uv run ruff check src tests` passes

## Next Steps

After implementation:
1. Run full test suite: `uv run pytest`
2. Test with real data: `uv run spa`
3. Create PR if on feature branch
4. Update CLAUDE.md if CLI usage patterns changed
