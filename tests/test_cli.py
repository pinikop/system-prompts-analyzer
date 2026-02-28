"""Tests for CLI interface."""


def test_cli_imports():
    """Verify CLI module can be imported."""
    try:
        from spa import cli

        assert hasattr(cli, "app")
    except ImportError:
        # Expected to fail until we create cli.py
        assert False, "cli module not yet created"
