import pathlib
from unittest.mock import MagicMock, patch
import pytest
import yaml
from click.testing import CliRunner

from src.main import cli


@pytest.fixture(autouse=True)
def clean_data_env(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    pathlib.Path("data").mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path: pathlib.Path) -> pathlib.Path:
    config_data = {
        "search": {
            "keywords": ["AI Engineer"],
            "location": "Bengaluru",
            "external_sites": [{"company": "Rearc", "url": "https://rearc.io"}],
        },
        "ai": {"provider": "ollama", "ollama": {"model_name": "llama3"}},
        "user": {
            "resume_path": "data/resume.pdf",
            "linkedin_connections_path": "data/Connections.csv",
        },
        "obsidian": {
            "vault_path": str(tmp_path / "vault"),
            "folders": {"jobs": "Jobs", "companies": "Companies", "people": "People", "analysis": "Analysis"},
        },
    }
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


def test_evaluate_companies_command(runner: CliRunner, mock_config: pathlib.Path):
    with patch("src.main.MindMapApp") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.evaluate_companies.return_value = [{"id": "rearc", "name": "Rearc", "score": 85}]
        mock_app_cls.return_value = mock_app

        result = runner.invoke(cli, ["evaluate-companies", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "Successfully evaluated and clustered 1 companies" in result.output


def test_companies_list_command(runner: CliRunner, mock_config: pathlib.Path):
    with patch("src.main.MindMapApp") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.list_companies.return_value = [
            {
                "id": "rearc",
                "name": "Rearc",
                "score": 85,
                "action_cluster": "Warm Outreach",
                "domain_cluster": "Generative AI & LLMs",
                "job_count": 2,
                "high_match_job_count": 2,
                "connection_count": 1,
                "key_connection_count": 1,
            }
        ]
        mock_app_cls.return_value = mock_app

        result = runner.invoke(cli, ["companies", "--config", str(mock_config), "--cluster", "warm"])
        assert result.exit_code == 0
        assert "Rearc" in result.output
        assert "Warm Outreach" in result.output


def test_company_details_command(runner: CliRunner, mock_config: pathlib.Path):
    with patch("src.main.MindMapApp") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.get_company_details.return_value = {
            "company": {
                "id": "rearc",
                "name": "Rearc",
                "score": 85,
                "action_cluster": "Warm Outreach",
                "domain_cluster": "Generative AI & LLMs",
                "target_tier": "Target",
                "evaluation_data": {"job_fit_score": 90, "company_fit_score": 95, "network_score": 60},
                "recommended_action": "Request internal referral from Shubham K before submitting application.",
            },
            "jobs": [
                {"id": "j1", "title": "AI Application Engineer", "relevance_score": 85, "link": "https://rearc.io/jobs"}
            ],
            "connections": [
                {
                    "name": "Shubham K",
                    "title": "Talent Acquisition Lead",
                    "role_type": "talent",
                    "connected_on": "2024-01-01",
                }
            ],
        }
        mock_app_cls.return_value = mock_app

        result = runner.invoke(cli, ["company", "Rearc", "--config", str(mock_config)])
        assert result.exit_code == 0
        assert "COMPANY: Rearc" in result.output
        assert "Warm Outreach" in result.output
        assert "AI Application Engineer" in result.output
        assert "Shubham K [TALENT]" in result.output
