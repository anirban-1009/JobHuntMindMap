import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.core.relevance_scorer import ScoringResult
from src.main import analyze_gaps, check, cli, login, network, score, scrape, search, test_ai


@pytest.fixture
def runner() -> CliRunner:
    """Provides a Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: pathlib.Path) -> str:
    """Creates a temporary valid configuration file."""
    config_path = tmp_path / "config.yaml"
    config_content = """
    search:
      keywords: ["Python"]
      location: "Active"
    ai:
      provider: "mock"
      api_key: "123"
    user:
      linkedin_connections_path: "data/Connections.csv"
    """
    config_path.write_text(config_content)
    return str(config_path)


class TestMainCLI:
    """Test suite for the MindMap main entry point and CLI commands."""

    def test_cli_help(self, runner: CliRunner) -> None:
        """Verify that the CLI help message is correctly displayed."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Job Hunt Mindmap CLI" in result.output

    def test_check_valid_config(self, runner: CliRunner, mock_config: str) -> None:
        """Verify the 'check' command validates a correct configuration file."""
        result = runner.invoke(check, ["--config", mock_config])
        assert result.exit_code == 0
        assert "Config file valid" in result.output

    def test_check_missing_config(self, runner: CliRunner) -> None:
        """Verify the 'check' command handles missing configuration files gracefully."""
        with runner.isolated_filesystem():
            result = runner.invoke(check, ["--config", "nonexistent.yaml"])
            assert result.exit_code == 1
            assert "Config file not found" in result.output

    def test_check_invalid_yaml(self, runner: CliRunner, tmp_path: pathlib.Path) -> None:
        """Verify the 'check' command handles malformed YAML files gracefully."""
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("key: value: error")
        result = runner.invoke(check, ["--config", str(bad_config)])
        assert result.exit_code == 1
        assert "Error parsing YAML" in result.output

    @patch("src.main.BrowserManager")
    def test_login_command(self, mock_browser_cls: MagicMock, runner: CliRunner) -> None:
        """Verify the 'login' command initiates a manual browser session."""
        mock_browser = mock_browser_cls.return_value.__enter__.return_value

        result = runner.invoke(login)

        assert result.exit_code == 0
        mock_browser.login_manual.assert_called_once()
        assert "Starting browser" in result.output

    @patch("src.main.BrowserManager")
    @patch("src.main.JobSearcher")
    def test_search_command(
        self, mock_searcher_cls: MagicMock, mock_browser_cls: MagicMock, runner: CliRunner, mock_config: str
    ) -> None:
        """Verify the 'search' command executes job discovery logic."""
        mock_searcher = mock_searcher_cls.return_value
        mock_result = MagicMock()
        mock_result.title = "Test Job"
        mock_result.id = "123"
        mock_result.company = "Test Co"
        mock_result.location = "Remote"
        mock_searcher.search.return_value = [mock_result]

        result = runner.invoke(search, ["--config", mock_config])

        assert result.exit_code == 0
        mock_searcher.search.assert_called()
        assert "Test Job" in result.output
        assert "Found 1 jobs" in result.output

    @patch("src.main.BrowserManager")
    @patch("src.main.JobSearcher")
    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.get_llm_client")
    def test_scrape_command(
        self,
        mock_get_llm: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_searcher_cls: MagicMock,
        mock_browser_cls: MagicMock,
        runner: CliRunner,
        mock_config: str,
    ) -> None:
        """Verify the 'scrape' command extracts and caches job details."""
        mock_searcher = mock_searcher_cls.return_value
        mock_search_result = MagicMock()
        mock_search_result.id = "123"
        mock_search_result.link = "http://example.com"
        mock_searcher.search.return_value = [mock_search_result]

        mock_extractor = mock_extractor_cls.return_value
        mock_job_details = MagicMock()
        mock_job_details.title = "Scraped Job"
        mock_job_details.company = "Scraped Co"
        mock_job_details.link = "http://example.com"
        mock_extractor.extract_multiple_jobs.return_value = [mock_job_details]

        result = runner.invoke(scrape, ["--config", mock_config])

        assert result.exit_code == 0
        mock_extractor.extract_multiple_jobs.assert_called()
        assert "Successfully scraped 1 / 1 jobs" in result.output

    @patch("src.main.get_llm_client")
    def test_test_ai_command(self, mock_get_llm: MagicMock, runner: CliRunner, mock_config: str) -> None:
        """Verify the 'test-ai' command validates LLM provider connectivity."""
        mock_client = mock_get_llm.return_value
        mock_client.generate.return_value = "Hello form AI"

        result = runner.invoke(test_ai, ["--config", mock_config])

        assert result.exit_code == 0
        assert "AI Response" in result.output
        assert "Hello form AI" in result.output

    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.NetworkGraphBuilder")
    def test_network_command(
        self,
        mock_builder_cls: MagicMock,
        mock_extractor_cls: MagicMock,
        runner: CliRunner,
        mock_config: str,
        tmp_path: pathlib.Path,
    ) -> None:
        """Verify the 'network' command identifies connections for a specific job."""
        conn_path = tmp_path / "data/Connections.csv"
        conn_path.parent.mkdir(parents=True)
        conn_path.touch()

        real_conn_path = tmp_path / "connections.csv"
        real_conn_path.touch()

        custom_config = tmp_path / "custom_config.yaml"
        custom_config.write_text(f'user:\n  linkedin_connections_path: "{real_conn_path}"')

        mock_extractor = mock_extractor_cls.return_value
        mock_job = MagicMock()
        mock_job.company = "Test Co"
        mock_extractor.get_cached_job.return_value = mock_job

        mock_builder = mock_builder_cls.return_value
        mock_match = MagicMock()
        mock_match.full_name = "Alice"
        mock_match.position = "Engineer"
        mock_match.metadata.last_contacted = "Yesterday"
        mock_match.metadata.achievements = ["Promo"]
        mock_builder.find_matches.return_value = [mock_match]

        result = runner.invoke(network, ["123", "--config", str(custom_config)])

        assert result.exit_code == 0
        assert "Found 1 connections" in result.output
        assert "Alice" in result.output

    @patch("src.main.get_llm_client")
    @patch("src.main.RelevanceScorer")
    @patch("src.main.JobDetailsExtractor")
    @patch("src.main.PDFResumeParser")
    def test_score_command(
        self,
        mock_parser_cls: MagicMock,
        mock_extractor_cls: MagicMock,
        mock_scorer_cls: MagicMock,
        mock_get_llm: MagicMock,
        runner: CliRunner,
        mock_config: str,
        tmp_path: pathlib.Path,
    ) -> None:
        """Verify the 'score' command evaluates job relevance against a resume."""
        resume_path = tmp_path / "resume.pdf"
        resume_path.touch()

        custom_config = tmp_path / "score_config.yaml"
        custom_config.write_text(f'ai: {{}}\nuser:\n  resume_path: "{resume_path}"')

        mock_extractor = mock_extractor_cls.return_value
        mock_job = MagicMock()
        mock_job.id = "123"
        mock_extractor.get_cached_job.return_value = mock_job
        mock_extractor.cache_dir = tmp_path

        mock_scorer = mock_scorer_cls.return_value
        mock_scorer.score_job.return_value = ScoringResult(
            score=85, matching_skills=["A"], missing_skills=["B"], reasoning="Good"
        )

        result = runner.invoke(score, ["123", "--config", str(custom_config)])

        assert result.exit_code == 0
        assert "Score 85" in result.output
        assert (tmp_path / "123_analysis.json").exists()

    @patch("src.main.GapAnalyzer")
    @patch("src.main.get_llm_client")
    def test_analyze_gaps_command(
        self,
        mock_get_llm: MagicMock,
        mock_analyzer_cls: MagicMock,
        runner: CliRunner,
        mock_config: str,
        tmp_path: pathlib.Path,
    ) -> None:
        """Verify the 'analyze-gaps' command identifies missing skills across jobs."""
        with runner.isolated_filesystem():
            conf = pathlib.Path("conf.yaml")
            conf.write_text("ai: {}")

            cache_dir = pathlib.Path("data/job_cache")
            cache_dir.mkdir(parents=True)

            analysis = {"score": 50, "matching_skills": [], "missing_skills": ["Python"], "reasoning": "Test"}
            (cache_dir / "1_analysis.json").write_text(json.dumps(analysis))

            mock_analyzer = mock_analyzer_cls.return_value
            gap_result = MagicMock()
            gap_result.skill_frequency = {"Python": 1}
            gap_result.improvement_plan = "Learn Python"
            mock_analyzer.analyze_gaps.return_value = gap_result

            result = runner.invoke(analyze_gaps, ["--config", "conf.yaml", "--min-score", "40"])

            assert result.exit_code == 0
            assert "Top Missing Skills" in result.output
            assert "Learn Python" in result.output
