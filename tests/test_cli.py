from click.testing import CliRunner

from src.main import check, cli


def test_cli_help():
    """Test that the CLI help command runs without error."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Job Hunt Mindmap CLI" in result.output


def test_check_missing_config():
    """Test that the check command fails gracefully when config is missing."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(check, ["--config", "nonexistent.yaml"])
        assert result.exit_code == 1
        assert "Config file not found" in result.output
