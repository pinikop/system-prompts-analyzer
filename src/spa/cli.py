"""CLI interface for System Prompts Analyzer."""

import logging
from pathlib import Path

import typer
from rich.console import Console

from spa.config import DEFAULT_LLM_MODEL, WEB_DATA_DIR
from spa.pipeline import run_pipeline

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        try:
            from importlib.metadata import version

            console.print(f"spa version {version('spa')}")
        except Exception:
            console.print("spa version unknown")
        raise typer.Exit()


@app.command()
def main(
    output: Path | None = typer.Option(
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
        "-f",
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
        help="Enable verbose logging",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-error output",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """Analyze coding assistant system prompts."""
    # Validate mutually exclusive flags
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(1)

    # Warn about ineffective flag combinations
    if skip_llm and llm_model != DEFAULT_LLM_MODEL:
        console.print(
            "[yellow]Warning: --llm-model has no effect when --skip-llm is set[/yellow]"
        )

    # Validate output path
    if output is not None:
        parent_dir = output.parent
        if not parent_dir.exists():
            console.print(
                f"[red]Error: Output directory does not exist: {parent_dir}[/red]"
            )
            console.print("Create the directory first or use a valid path.")
            raise typer.Exit(1)

    # Set up logging based on verbosity
    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(levelname)s: %(message)s",
    )

    # Suppress LiteLLM's verbose logging unless --verbose
    litellm_logger = logging.getLogger("LiteLLM")
    if verbose:
        litellm_logger.setLevel(logging.DEBUG)
    else:
        litellm_logger.setLevel(logging.ERROR)  # Only show errors

    # Determine output path
    output_path = output if output is not None else WEB_DATA_DIR / "analysis.json"

    # Run the pipeline
    result = run_pipeline(
        output_path=output_path,
        skip_llm=skip_llm,
        llm_model=llm_model,
        previous_analysis_path=output_path if not force else None,
        force=force,
        skip_update=skip_update,
    )

    # Report results
    count = result["meta"]["prompt_count"]
    assistants = result["meta"]["assistant_count"]
    llm_status = (
        f" (LLM: {result['meta']['llm_model']})" if result["meta"]["llm_model"] else ""
    )

    if not quiet:
        console.print(
            f"[green]✓[/green] Analyzed {count} prompts from {assistants} assistants{llm_status}"
        )
        console.print(f"  → {output_path}")


if __name__ == "__main__":
    app()
