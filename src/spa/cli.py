"""CLI interface for System Prompts Analyzer."""

from pathlib import Path

import typer
from rich.console import Console

from spa.config import DEFAULT_LLM_MODEL

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
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

    console.print(f"Output: {output}")
    console.print(f"Skip LLM: {skip_llm}")
    console.print(f"LLM Model: {llm_model}")
    console.print(f"Force: {force}")
    console.print(f"Skip Update: {skip_update}")
    console.print(f"Verbose: {verbose}")
    console.print(f"Quiet: {quiet}")


if __name__ == "__main__":
    app()
