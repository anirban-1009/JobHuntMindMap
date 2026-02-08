import json
import pathlib
import shutil
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from src.core.relevance_scorer import ScoringResult
from src.main import cli


@pytest.fixture(autouse=True)
def clean_data_env() -> Generator[None, None, None]:
    """Ensure a clean 'data' directory environment for each test."""
    data_dir = pathlib.Path("data")

    def _cleanup():
        if data_dir.exists():
            for item in data_dir.iterdir():
                if item.name == ".gitkeep":
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            data_dir.mkdir(parents=True, exist_ok=True)

    _cleanup()
    yield
    _cleanup()


@pytest.fixture
def runner() -> CliRunner:
    """Provides a Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: pathlib.Path) -> pathlib.Path:
    """Creates a temporary configuration file with standard mock values."""
    config_data = {
        "search": {"keywords": ["Python"], "location": "Remote", "location_type": "Remote", "filters": {}},
        "ai": {"provider": "ollama", "ollama": {"model_name": "llama3"}},
        "user": {"resume_path": "data/resume.pdf", "email": "user@example.com"},
        "notifications": {"email": {"enabled": True}},
    }
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


class TestCLIValidation:
    """Validation tests for configuration and connectivity commands."""

    def test_check_valid_config(self, runner: CliRunner, mock_config: pathlib.Path) -> None:
        """Verify the 'check' command validates a correct configuration file."""
        result = runner.invoke(cli, ["check", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Config file valid" in result.output

    @patch("src.main.get_llm_client")
    def test_test_ai_command_success(
        self, mock_get_client: MagicMock, runner: CliRunner, mock_config: pathlib.Path
    ) -> None:
        """Verify the 'test-ai' command displays successful AI responses."""
        mock_client = MagicMock()
        mock_client.generate.return_value = "AI Response"
        mock_get_client.return_value = mock_client

        result = runner.invoke(cli, ["test-ai", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "AI Response (ollama):" in result.output
        assert "AI Response" in result.output

    @patch("src.main.get_llm_client")
    def test_test_ai_command_empty_response(
        self, mock_get_client: MagicMock, runner: CliRunner, mock_config: pathlib.Path
    ) -> None:
        """Verify the 'test-ai' command handles empty AI responses gracefully."""
        mock_client = MagicMock()
        mock_client.generate.return_value = ""
        mock_get_client.return_value = mock_client

        result = runner.invoke(cli, ["test-ai", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "AI returned empty response" in result.output


class TestCLIJobIngestion:
    """Tests for job discovery, scraping, and session management."""

    @patch("src.main.BrowserManager")
    @patch("src.main.JobSearcher")
    def test_search_command(
        self,
        mock_searcher_class: MagicMock,
        mock_browser_manager_class: MagicMock,
        runner: CliRunner,
        mock_config: pathlib.Path,
    ) -> None:
        """Verify the 'search' command initiates job discovery via browser."""
        mock_searcher = mock_searcher_class.return_value
        mock_searcher.search.return_value = [MagicMock(id="1", title="Job 1", company="Co 1", location="Loc 1")]
        mock_browser_manager_class.return_value.__enter__.return_value = MagicMock()

        result = runner.invoke(cli, ["search", "--config", str(mock_config), "--headless"])
        assert result.exit_code == 0
        assert "Total unique jobs found: 1" in result.output
        assert "Job 1" in result.output

    @patch("src.main.BrowserManager")
    @patch("src.main.JobSearcher")
    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.get_llm_client")
    def test_scrape_command(
        self,
        mock_get_llm: MagicMock,
        mock_extractor_class: MagicMock,
        mock_searcher_class: MagicMock,
        mock_browser_manager_class: MagicMock,
        runner: CliRunner,
        mock_config: pathlib.Path,
    ) -> None:
        """Verify the 'scrape' command handles multi-step job extraction logic."""
        mock_searcher = mock_searcher_class.return_value
        mock_searcher.search.return_value = [MagicMock(id="1", title="Job 1", company="Co 1")]
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.extract_multiple_jobs.return_value = [MagicMock(title="Job 1", company="Co 1", link="url")]
        mock_browser_manager_class.return_value.__enter__.return_value = MagicMock()

        result = runner.invoke(cli, ["scrape", "--config", str(mock_config), "--limit", "1"])
        assert result.exit_code == 0
        assert "Successfully scraped 1 / 1 jobs" in result.output

    @patch("src.main.BrowserManager")
    def test_login_command(
        self, mock_browser_manager_class: MagicMock, runner: CliRunner, mock_config: pathlib.Path
    ) -> None:
        """Verify the 'login' command initiates a manual browser session for cookie retrieval."""
        mock_browser = MagicMock()
        mock_browser_manager_class.return_value.__enter__.return_value = mock_browser

        result = runner.invoke(cli, ["login", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Starting browser for manual login" in result.output
        mock_browser.login_manual.assert_called_once()


class TestCLIJobAnalysis:
    """Tests for scoring, networking, and gap analysis commands."""

    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.NetworkGraphBuilder")
    def test_network_command(
        self,
        mock_builder_class: MagicMock,
        mock_extractor_class: MagicMock,
        runner: CliRunner,
        mock_config: pathlib.Path,
    ) -> None:
        """Verify the 'network' command identifies connections for a cached job."""
        mock_extractor = mock_extractor_class.return_value
        mock_job = MagicMock(id="1", company="TestCo")
        mock_extractor.get_cached_job.return_value = mock_job
        mock_builder = mock_builder_class.return_value
        mock_builder.find_matches.return_value = [MagicMock(full_name="Alice", position="Engineer")]

        pathlib.Path("data/sample_connections.csv").touch()

        result = runner.invoke(cli, ["network", "1", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Found 1 connections at TestCo:" in result.output
        assert "Alice" in result.output

    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.get_llm_client")
    @patch("src.main.PDFResumeParser")
    @patch("src.main.RelevanceScorer")
    def test_score_command(
        self,
        mock_scorer_class: MagicMock,
        mock_parser_class: MagicMock,
        mock_get_llm: MagicMock,
        mock_extractor_class: MagicMock,
        runner: CliRunner,
        mock_config: pathlib.Path,
    ) -> None:
        """Verify the 'score' command evaluates job relevance scores."""
        mock_parser = mock_parser_class.return_value
        mock_parser.extract_text.return_value = "Resume Text"
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.get_cached_job.return_value = MagicMock(id="1")
        mock_extractor.cache_dir = pathlib.Path("data/job_cache")
        mock_extractor.cache_dir.mkdir(parents=True, exist_ok=True)
        mock_scorer = mock_scorer_class.return_value
        mock_scorer.score_job.return_value = ScoringResult(
            score=85, matching_skills=["A"], missing_skills=["B"], reasoning="Great fit"
        )
        pathlib.Path("data/sample_resume.pdf").touch()

        result = runner.invoke(cli, ["score", "1", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Scoring 1 jobs..." in result.output
        assert "Score 85" in result.output

    @patch("src.main.GapAnalyzer")
    @patch("src.main.get_llm_client")
    def test_analyze_gaps_command(
        self, mock_get_llm: MagicMock, mock_analyzer_class: MagicMock, runner: CliRunner, mock_config: pathlib.Path
    ) -> None:
        """Verify the 'analyze-gaps' command identifies missing skills across all scored jobs."""
        mock_analyzer = mock_analyzer_class.return_value
        mock_analyzer.analyze_gaps.return_value = MagicMock(
            skill_frequency={"Python": 2}, improvement_plan="Learn Python"
        )
        job_cache = pathlib.Path("data/job_cache")
        job_cache.mkdir(parents=True, exist_ok=True)
        analysis_file = job_cache / "gap_analysis_test_analysis.json"
        with open(analysis_file, "w") as f:
            json.dump({"score": 80, "matching_skills": ["A"], "missing_skills": ["B"], "reasoning": "R"}, f)

        result = runner.invoke(cli, ["analyze-gaps", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Analyzing gaps across 1 jobs..." in result.output
        assert "Python: 2 jobs" in result.output

    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.EmailService")
    def test_notify_command(
        self,
        mock_service_class: MagicMock,
        mock_extractor_class: MagicMock,
        runner: CliRunner,
        mock_config: pathlib.Path,
    ) -> None:
        """Verify the 'notify' command sends digests for high-scoring jobs."""
        job_cache = pathlib.Path("data/job_cache")
        job_cache.mkdir(parents=True, exist_ok=True)
        analysis_file = job_cache / "notify_test_analysis.json"
        with open(analysis_file, "w") as f:
            json.dump({"score": 80, "matching_skills": ["A"], "missing_skills": ["B"], "reasoning": "R"}, f)
        mock_extractor = mock_extractor_class.return_value
        mock_extractor.get_cached_job.return_value = MagicMock(id="notify_test")
        mock_service = mock_service_class.return_value
        mock_service.send_job_digest.return_value = True

        result = runner.invoke(cli, ["notify", "--config", str(mock_config), "--min-score", "70"])
        assert result.exit_code == 0
        assert "Sending digest" in result.output
        assert "Notifications sent successfully" in result.output
