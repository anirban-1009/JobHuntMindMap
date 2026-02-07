import pathlib
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from src.main import cli


class TestCLICommands:
    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_config(self, tmp_path):
        config_data = {
            "search": {"keywords": ["Python"], "location": "Remote", "location_type": "Remote", "filters": {}},
            "ai": {"provider": "ollama", "ollama": {"model_name": "llama3"}},
        }
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        return config_file

    def test_check_valid_config(self, runner, mock_config):
        """Test 'check' command with a valid config."""
        result = runner.invoke(cli, ["check", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Config file valid" in result.output

    @patch("src.ingest.browser_manager.BrowserManager")
    @patch("src.ingest.job_searcher.JobSearcher")
    def test_search_command(self, mock_searcher_class, mock_browser_manager_class, runner, mock_config):
        """Test 'search' command."""
        mock_searcher = mock_searcher_class.return_value
        mock_searcher.search.return_value = [MagicMock(id="1", title="Job 1", company="Co 1", location="Loc 1")]

        # Ensure data dir exists
        pathlib.Path("data").mkdir(exist_ok=True)

        result = runner.invoke(cli, ["search", "--config", str(mock_config), "--headless"])
        assert result.exit_code == 0
        assert "Total unique jobs found: 1" in result.output
        assert "Job 1" in result.output

    @patch("src.ingest.browser_manager.BrowserManager")
    @patch("src.ingest.job_searcher.JobSearcher")
    @patch("src.ingest.job_details_extractor.JobDetailsExtractor")
    def test_scrape_command(
        self, mock_extractor_class, mock_searcher_class, mock_browser_manager_class, runner, mock_config
    ):
        """Test 'scrape' command."""
        mock_searcher = mock_searcher_class.return_value
        mock_searcher.search.return_value = [MagicMock(id="1", title="Job 1", company="Co 1")]

        mock_extractor = mock_extractor_class.return_value
        mock_extractor.extract_multiple_jobs.return_value = [MagicMock(title="Job 1", company="Co 1", link="url")]

        result = runner.invoke(cli, ["scrape", "--config", str(mock_config), "--limit", "1"])
        assert result.exit_code == 0
        assert "Successfully scraped 1 / 1 jobs" in result.output

    @patch("src.core.llm_client.get_llm_client")
    def test_test_ai_command(self, mock_get_client, runner, mock_config):
        """Test 'test-ai' command."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "AI Response"
        mock_get_client.return_value = mock_client

        result = runner.invoke(cli, ["test-ai", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "AI Response (ollama):" in result.output
        assert "AI Response" in result.output

    @patch("src.core.llm_client.get_llm_client")
    def test_test_ai_command_empty_response(self, mock_get_client, runner, mock_config):
        """Test 'test-ai' command with empty response."""
        mock_client = MagicMock()
        mock_client.generate.return_value = ""
        mock_get_client.return_value = mock_client

        result = runner.invoke(cli, ["test-ai", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "AI returned an empty response" in result.output

    @patch("src.ingest.browser_manager.BrowserManager")
    def test_login_command(self, mock_browser_manager_class, runner, mock_config):
        """Test 'login' command."""
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value.__enter__.return_value = mock_browser

        result = runner.invoke(cli, ["login", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Starting browser for manual login" in result.output
        mock_browser.login_manual.assert_called_once()
