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


def test_cli_help():
    """CLI should show help text."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "System Prompts Analyzer" in result.stdout
