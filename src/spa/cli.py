"""CLI interface for System Prompts Analyzer."""

import typer
from rich.console import Console

console = Console()

app = typer.Typer(
    name="spa",
    help="System Prompts Analyzer - analyze coding assistant prompts",
    add_completion=True,
)


@app.command()
def main() -> None:
    """Analyze coding assistant system prompts."""
    console.print("Hello from typer CLI!")


if __name__ == "__main__":
    app()
