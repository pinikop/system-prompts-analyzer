"""CLI interface for System Prompts Analyzer."""

import functools
import http.server
import logging
import socket
import webbrowser
from pathlib import Path

import typer
from rich.console import Console

from spa.config import DEFAULT_LLM_MODEL, WEB_DATA_DIR
from spa.pipeline import PipelineError, run_pipeline

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()


def find_free_port(start: int, max_attempts: int = 10) -> int:
    """Return the first free TCP port starting from `start`."""
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{start + max_attempts - 1}")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        try:
            from importlib.metadata import version

            console.print(f"spa version {version('spa')}")
        except Exception:
            console.print("spa version unknown")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
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
    if ctx.invoked_subcommand is not None:
        return
    # Validate mutually exclusive flags
    if verbose and quiet:
        console.print("[red]Error: --verbose and --quiet are mutually exclusive[/red]")
        raise typer.Exit(1)

    # Warn about ineffective flag combinations
    if skip_llm and llm_model != DEFAULT_LLM_MODEL:
        console.print("[yellow]Warning: --llm-model has no effect when --skip-llm is set[/yellow]")

    # Validate output path
    if output is not None:
        parent_dir = output.parent
        if not parent_dir.exists():
            console.print(f"[red]Error: Output directory does not exist: {parent_dir}[/red]")
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
    try:
        result = run_pipeline(
            output_path=output_path,
            skip_llm=skip_llm,
            llm_model=llm_model,
            previous_analysis_path=output_path if not force else None,
            force=force,
            skip_update=skip_update,
        )
    except PipelineError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    # Report results
    count = result["meta"]["prompt_count"]
    assistants = result["meta"]["assistant_count"]
    llm_status = f" (LLM: {result['meta']['llm_model']})" if result["meta"]["llm_model"] else ""

    if not quiet:
        console.print(
            f"[green]✓[/green] Analyzed {count} prompts from {assistants} assistants{llm_status}"
        )
        console.print(f"  → {output_path}")


@app.command()
def serve(
    port: int = typer.Option(8000, "--port", help="Starting port to try"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser automatically"),
) -> None:
    """Start a local HTTP server for the web dashboard."""
    analysis = WEB_DATA_DIR / "analysis.json"
    if not analysis.exists():
        console.print("[red]No analysis found. Run 'spa' first to generate data.[/red]")
        raise typer.Exit(1)

    try:
        actual_port = find_free_port(port)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1) from e

    web_dir = str(WEB_DATA_DIR.parent)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=web_dir)
    url = f"http://localhost:{actual_port}"

    with http.server.HTTPServer(("localhost", actual_port), handler) as httpd:
        console.print(f"Serving at [link={url}]{url}[/link]  (Ctrl+C to stop)")
        if not no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[green]Stopped.[/green]")


if __name__ == "__main__":
    app()
