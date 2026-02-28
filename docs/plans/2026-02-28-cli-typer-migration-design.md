# CLI Migration to Typer Design

## Context

The current CLI uses argparse with 5 flags. A TODO in the hybrid data fetching design doc suggests migrating to typer for better UX (auto-completion, validation). This design covers a full migration to typer with Rich integration for modern CLI experience.

## Requirements

**Backward Compatibility:**
- Maintain all current flags: `--output` / `-o`, `--skip-llm`, `--llm-model`, `--force`, `--skip-update`
- Preserve current behavior and defaults

**New Features:**
- Input validation (paths exist, valid model names, flag combinations)
- Shell completion (bash/zsh/fish)
- Better help organization with examples
- Verbosity control (`--verbose`/`--quiet` for logging levels)
- `--version` flag
- Rich integration for colored output and better formatting

## Architecture

**File Structure:**
```
src/spa/
├── cli.py          # NEW: Typer CLI layer
├── pipeline.py     # MODIFIED: Remove old main(), keep run_pipeline()
└── ...
```

**Separation of Concerns:**
- `cli.py` - Argument parsing, validation, user interaction, output formatting
- `pipeline.py` - Data processing, metrics, LLM analysis (business logic)

**Entry Point Change:**
```toml
# pyproject.toml
[project.scripts]
spa = "spa.cli:app"  # Changed from spa.pipeline:main
```

**Benefits:**
- Testable CLI separate from business logic
- Pipeline importable for programmatic use
- Future CLI changes isolated from core logic

## Components

### Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    "typer>=0.12",
    "rich>=13.0",
    # ... existing deps
]
```

### CLI Structure (cli.py)

```python
import typer
from rich.console import Console
from rich.progress import Progress

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
)
console = Console()

@app.command()
def main(
    output: Path = typer.Option(None, "-o", "--output", help="..."),
    skip_llm: bool = typer.Option(False, "--skip-llm", help="..."),
    llm_model: str = typer.Option(DEFAULT_LLM_MODEL, "--llm-model", help="..."),
    force: bool = typer.Option(False, "--force", help="..."),
    skip_update: bool = typer.Option(False, "--skip-update", help="..."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="..."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="..."),
):
    """Analyze coding assistant system prompts."""
    # Validation, setup logging, call pipeline.run_pipeline()
```

### Validation

**Path Validation:**
- If `--output` provided, ensure parent directory exists
- Validate DATA_DIR and WEB_DATA_DIR are accessible

**Flag Validation:**
- `--verbose` and `--quiet` are mutually exclusive
- If `--skip-llm` is set, `--llm-model` has no effect (warn user)

**Model Validation (optional):**
- Could validate against known model prefixes (gpt-, claude-, etc.)
- Or just pass through and let litellm handle it

### Logging Setup

Based on verbosity flags:
- Default: INFO level
- `--verbose`: DEBUG level
- `--quiet`: WARNING level only

### Output Formatting with Rich

**Success Output:**
```
✓ Analyzed 26 prompts from 8 assistants (LLM: qwen-max)
  → web/data/analysis.json
```

**Progress Indication:**
```
Running LLM analysis...
  ⠋ claude-code::v1.0 [1/3]
  ✓ claude-code::v1.0 (1234 tokens)
  ⠋ cursor::gpt4 [2/3]
```

**Error Messages:**
```
✗ Error: Output directory does not exist: /invalid/path
  Use --output with a valid path or create the directory first.
```

### Help Text Organization

Group related options:
```
Analysis Options:
  --skip-llm          Skip LLM analysis
  --llm-model TEXT    LLM model to use [default: qwen-max]
  --force             Reprocess everything, ignore cache

Data Options:
  --skip-update       Don't check upstream, use local data

Output Options:
  -o, --output PATH   Output JSON path [default: web/data/analysis.json]
  -v, --verbose       Enable verbose logging
  -q, --quiet         Suppress non-error output

Other Options:
  --version           Show version and exit
  --help              Show this message and exit

Examples:
  spa                           # Full analysis with LLM
  spa --skip-llm                # Metrics only, no LLM
  spa --force                   # Reprocess everything
  spa --llm-model gpt-4o        # Use specific model
```

### Version Flag

Add version to `pyproject.toml`:
```toml
[project]
version = "0.2.0"  # Bump for this feature
```

Access in CLI:
```python
from importlib.metadata import version

@app.callback()
def callback(
    version_flag: bool = typer.Option(None, "--version", callback=version_callback)
):
    pass

def version_callback(value: bool):
    if value:
        console.print(f"spa version {version('spa')}")
        raise typer.Exit()
```

### Shell Completion

Users install with:
```bash
spa --install-completion bash  # or zsh, fish
```

Typer handles this automatically with `add_completion=True`.

## Migration Strategy

**Backward Compatibility:**
1. All existing flags work exactly as before
2. Short forms preserved (`-o` for `--output`)
3. Defaults unchanged
4. Output format compatible (can enhance with Rich but not break parsing)

**Changes:**
- Entry point: `pyproject.toml` script changes to `spa.cli:app`
- Old `main()` in `pipeline.py` removed (already extracted as `run_pipeline()`)
- New flags are additions, not breaking changes

## Testing Strategy

**Unit Tests (tests/test_cli.py):**
```python
from typer.testing import CliRunner
from spa.cli import app

runner = CliRunner()

def test_default_flags():
    result = runner.invoke(app, [])
    assert result.exit_code == 0

def test_skip_llm():
    result = runner.invoke(app, ["--skip-llm"])
    assert result.exit_code == 0
    assert "LLM:" not in result.stdout

def test_verbose_quiet_conflict():
    result = runner.invoke(app, ["--verbose", "--quiet"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.stdout.lower()

def test_output_validation():
    result = runner.invoke(app, ["--output", "/invalid/nonexistent/path.json"])
    assert result.exit_code != 0
    assert "directory does not exist" in result.stdout.lower()
```

**Integration Tests:**
- Existing pipeline tests continue to work (they import `run_pipeline()`)
- Add CLI-specific tests for flag combinations

## Error Handling

**Validation Errors:**
- Use `typer.BadParameter` for invalid inputs
- Rich formatting for clear error messages
- Exit code 2 for validation errors

**Pipeline Errors:**
- Catch exceptions from `run_pipeline()`
- Format with Rich console.print_exception()
- Exit code 1 for runtime errors

**User-Friendly Messages:**
- Don't show stack traces by default (unless `--verbose`)
- Suggest fixes where possible ("Create directory first", "Check API key in .env")

## Implementation Steps

High-level overview (detailed plan follows):

1. Add typer and rich dependencies
2. Create `src/spa/cli.py` with basic structure
3. Migrate all existing flags with validation
4. Add new flags (`--verbose`, `--quiet`, `--version`)
5. Integrate Rich for output formatting
6. Update entry point in `pyproject.toml`
7. Remove old `main()` from `pipeline.py`
8. Write CLI tests
9. Update documentation (README.md, help text)
10. Test shell completion installation

## Success Criteria

- All existing flags work identically
- New flags provide advertised functionality
- Shell completion works in bash/zsh/fish
- Help text is clear and well-organized
- Error messages are helpful and colored
- Tests cover all flag combinations
- Documentation updated

## Future Enhancements (Out of Scope)

- Interactive mode for selecting assistants to analyze
- Subcommands (e.g., `spa analyze`, `spa compare`, `spa serve`)
- Configuration file support (.spa.toml)
- Watch mode for auto-reprocessing on file changes
