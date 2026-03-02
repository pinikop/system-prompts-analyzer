"""Tests for CLI interface."""

from typer.testing import CliRunner


def test_cli_imports():
    """Verify CLI module can be imported."""
    from spa import cli

    assert hasattr(cli, "app")


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
    assert result.exit_code == 0


def test_output_flag_long():
    """Test --output flag for output path."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--output", "test.json"])
    assert result.exit_code == 0


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
    assert result.exit_code == 0


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


def test_output_path_validation_invalid_parent():
    """Test that invalid output parent directory is caught."""
    from spa.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--output", "/nonexistent/dir/output.json"])
    # Should fail with validation error
    assert result.exit_code != 0
    assert "directory" in result.stdout.lower() or "not exist" in result.stdout.lower()


def test_output_path_validation_valid(tmp_path):
    """Test that valid output path is accepted."""
    from spa.cli import app

    output_file = tmp_path / "output.json"
    runner = CliRunner()
    result = runner.invoke(app, ["--output", str(output_file)])
    # Should succeed (validation passes)
    assert result.exit_code == 0


def test_pipeline_integration_skip_llm(tmp_path):
    """Test that CLI integrates with pipeline (skip LLM for speed)."""
    from spa.cli import app

    output_file = tmp_path / "test_output.json"
    runner = CliRunner()
    result = runner.invoke(app, ["--skip-llm", "--output", str(output_file)])

    # Should complete successfully
    assert result.exit_code == 0
    # Output file should be created
    assert output_file.exists()
    # Should contain valid JSON
    import json

    data = json.loads(output_file.read_text())
    assert "prompts" in data
    assert "meta" in data


def test_llm_model_with_skip_llm_warning(tmp_path):
    """Test that --llm-model with --skip-llm shows warning."""
    from spa.cli import app

    output_file = tmp_path / "test_output.json"
    runner = CliRunner()
    result = runner.invoke(
        app, ["--skip-llm", "--llm-model", "gpt-4o", "--output", str(output_file)]
    )

    # Should still succeed
    assert result.exit_code == 0
    # Should show warning
    assert "warning" in result.stdout.lower()
    assert "no effect" in result.stdout.lower()
