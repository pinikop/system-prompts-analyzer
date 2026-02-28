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
    assert "Analyze coding assistant system prompts" in result.stdout


def test_output_flag_short():
    """Test -o flag for output path."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["-o", "test.json"])
    # Should not error on flag parsing
    assert result.exit_code == 0 or "test.json" in str(result.exception)


def test_output_flag_long():
    """Test --output flag for output path."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--output", "test.json"])
    assert result.exit_code == 0 or "test.json" in str(result.exception)


def test_skip_llm_flag():
    """Test --skip-llm flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--skip-llm"])
    assert result.exit_code == 0


def test_llm_model_flag():
    """Test --llm-model flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--llm-model", "gpt-4o"])
    # Should accept model parameter
    assert result.exit_code == 0 or "gpt-4o" in str(result.exception)


def test_force_flag():
    """Test --force flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--force"])
    assert result.exit_code == 0


def test_skip_update_flag():
    """Test --skip-update flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--skip-update"])
    assert result.exit_code == 0


def test_verbose_flag():
    """Test --verbose flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--verbose"])
    assert result.exit_code == 0


def test_verbose_flag_short():
    """Test -v flag for verbose."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["-v"])
    assert result.exit_code == 0


def test_quiet_flag():
    """Test --quiet flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--quiet"])
    assert result.exit_code == 0


def test_quiet_flag_short():
    """Test -q flag for quiet."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["-q"])
    assert result.exit_code == 0


def test_verbose_quiet_mutual_exclusion():
    """Test that --verbose and --quiet cannot be used together."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--verbose", "--quiet"])
    # Should fail with mutually exclusive error
    assert result.exit_code != 0


def test_version_flag():
    """Test --version flag."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    # Version flag should exit successfully
    assert result.exit_code == 0
    # Should contain version string
    assert "spa" in result.stdout.lower() or "version" in result.stdout.lower()
