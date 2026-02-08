import json
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.core.relevance_scorer import ScoringResult
from src.main import analyze_gaps, check, cli, login, network, score, scrape, search, test_ai


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Creates a temporary valid config file."""
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


def test_cli_help(runner):
    """Test that the CLI help command runs without error."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Job Hunt Mindmap CLI" in result.output


def test_check_valid_config(runner, mock_config):
    """Test check command with valid config."""
    result = runner.invoke(check, ["--config", mock_config])
    assert result.exit_code == 0
    assert "Config file valid" in result.output


def test_check_missing_config(runner):
    """Test check command fails gracefully when config is missing."""
    with runner.isolated_filesystem():
        result = runner.invoke(check, ["--config", "nonexistent.yaml"])
        assert result.exit_code == 1
        assert "Config file not found" in result.output


def test_check_invalid_yaml(runner, tmp_path):
    """Test check command with invalid YAML."""
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("key: value: error")
    result = runner.invoke(check, ["--config", str(bad_config)])
    assert result.exit_code == 1
    assert "Error parsing YAML" in result.output


@patch("src.ingest.browser_manager.BrowserManager")
def test_login_command(mock_browser_cls, runner):
    """Test login command invokes manual login."""
    mock_browser = mock_browser_cls.return_value.__enter__.return_value

    result = runner.invoke(login)

    assert result.exit_code == 0
    mock_browser.login_manual.assert_called_once()
    assert "Starting browser" in result.output


@patch("src.ingest.browser_manager.BrowserManager")
@patch("src.ingest.job_searcher.JobSearcher")
def test_search_command(mock_searcher_cls, mock_browser_cls, runner, mock_config):
    """Test search command."""
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


@patch("src.ingest.browser_manager.BrowserManager")
@patch("src.ingest.job_searcher.JobSearcher")
@patch("src.ingest.job_details_extractor.JobDetailsExtractor")
@patch("src.core.ai.get_llm_client")
def test_scrape_command(mock_get_llm, mock_extractor_cls, mock_searcher_cls, mock_browser_cls, runner, mock_config):
    """Test scrape command."""
    mock_searcher = mock_searcher_cls.return_value
    mock_search_result = MagicMock()
    mock_search_result.id = "123"
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
    assert "Scraped Job" in result.output


@patch("src.core.llm_client.get_llm_client")
def test_test_ai_command(mock_get_llm, runner, mock_config):
    """Test test_ai command."""
    mock_client = mock_get_llm.return_value
    mock_client.generate.return_value = "Hello form AI"

    result = runner.invoke(test_ai, ["--config", mock_config])

    assert result.exit_code == 0
    assert "AI Response" in result.output
    assert "Hello form AI" in result.output


@patch("src.ingest.job_details_extractor.JobDetailsExtractor")
@patch("src.core.network_graph.NetworkGraphBuilder")
def test_network_command(mock_builder_cls, mock_extractor_cls, runner, mock_config, tmp_path):
    """Test network command."""
    # Ensure connections path exists to pass validation
    conn_path = tmp_path / "data/Connections.csv"
    conn_path.parent.mkdir(parents=True)
    conn_path.touch()

    # Needs to update mock config to point to this temp path because the command reads it
    # We can rely on the default logic or just patch pathlib.Path.exists for the specific check
    # But simpler to just make the file exist at data/Connections.csv relative to CWD?
    # No, CWD is isolated by runner? No, isolated_filesystem is not used here.
    # Let's verify what mock_config has. It points to "data/Connections.csv".
    # So we need that file to exist relative to where test runs.
    # Actually, we can just point config to our tmp file.
    real_conn_path = tmp_path / "connections.csv"
    real_conn_path.touch()

    custom_config = tmp_path / "custom_config.yaml"
    custom_config.write_text(
        f"""
    user:
      linkedin_connections_path: "{real_conn_path}"
    """
    )

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


@patch("src.core.ai.get_llm_client")
@patch("src.core.relevance_scorer.RelevanceScorer")
@patch("src.ingest.job_details_extractor.JobDetailsExtractor")
@patch("src.ingest.resume_parser.PDFResumeParser")
def test_score_command(
    mock_parser_cls, mock_extractor_cls, mock_scorer_cls, mock_get_llm, runner, mock_config, tmp_path
):
    """Test score command."""
    # Need a resume file
    resume_path = tmp_path / "resume.pdf"
    resume_path.touch()

    custom_config = tmp_path / "score_config.yaml"
    custom_config.write_text(
        f"""
    ai: {{}}
    user:
      resume_path: "{resume_path}"
    """
    )

    mock_extractor = mock_extractor_cls.return_value
    mock_job = MagicMock()
    mock_job.id = "123"
    mock_extractor.get_cached_job.return_value = mock_job
    # Mock cache dir for file output
    mock_extractor.cache_dir = tmp_path

    mock_scorer = mock_scorer_cls.return_value
    mock_scorer.score_job.return_value = ScoringResult(
        score=85, matching_skills=["A"], missing_skills=["B"], reasoning="Good"
    )

    result = runner.invoke(score, ["123", "--config", str(custom_config)])

    assert result.exit_code == 0
    assert "Score 85" in result.output
    assert (tmp_path / "123_analysis.json").exists()


@patch("src.core.gap_analysis.GapAnalyzer")
@patch("src.core.ai.get_llm_client")
def test_analyze_gaps_command(mock_get_llm, mock_analyzer_cls, runner, mock_config, tmp_path):
    """Test analyze_gaps command."""
    # We need to mock reading some JSON files from data/job_cache
    # The command hardcodes "data/job_cache". This is problematic for testing without isolation.
    # We should patch pathlib.Path or run in isolated filesystem.

    with runner.isolated_filesystem():
        # Setup config in isolated env
        conf = pathlib.Path("conf.yaml")
        conf.write_text("ai: {}")

        # Setup cache data
        cache_dir = pathlib.Path("data/job_cache")
        cache_dir.mkdir(parents=True)

        analysis = {"score": 50, "matching_skills": [], "missing_skills": ["Python"], "reasoning": "Test"}
        (cache_dir / "1_analysis.json").write_text(json.dumps(analysis))

        # Mock analyzer
        mock_analyzer = mock_analyzer_cls.return_value
        # Use MagicMock for the return value of analyze_gaps to allow attribute access
        gap_result = MagicMock()
        gap_result.skill_frequency = {"Python": 1}
        gap_result.improvement_plan = "Learn Python"
        mock_analyzer.analyze_gaps.return_value = gap_result

        result = runner.invoke(analyze_gaps, ["--config", "conf.yaml", "--min-score", "40"])

        assert result.exit_code == 0
        assert "Top Missing Skills" in result.output
        assert "Learn Python" in result.output
