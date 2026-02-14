import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.generator.sync_service import SyncService
from src.ingest.job_details_extractor import JobDetails


class TestSyncService:
    @pytest.fixture
    def mock_config(self):
        return {"obsidian": {"vault_path": "/tmp/vault", "folders": {"jobs": "Jobs", "companies": "Companies"}}}

    @pytest.fixture
    def sync_service(self, mock_config):
        with (
            patch("src.generator.sync_service.VaultManager"),
            patch("src.generator.sync_service.TemplateManager"),
            patch("src.generator.sync_service.DashboardGenerator"),
            patch("src.generator.sync_service.JobDetailsExtractor"),
        ):
            return SyncService(mock_config)

    def test_determine_specialization_ai_ml(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Senior Machine Learning Engineer (AI/NLP)"
        assert sync_service._determine_specialization(job) == "AI_ML"

        job.title = "LLM Researcher"
        assert sync_service._determine_specialization(job) == "AI_ML"

    def test_determine_specialization_python(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Django Backend Developer"
        assert sync_service._determine_specialization(job) == "Python_Dev"

    def test_determine_specialization_backend(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Platform Engineer (API)"
        assert sync_service._determine_specialization(job) == "Backend"

    def test_determine_specialization_frontend(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "React Web Developer"
        assert sync_service._determine_specialization(job) == "Frontend"

    def test_determine_specialization_devops(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Kubernetes Infrastructure Specialist"
        assert sync_service._determine_specialization(job) == "DevOps_Cloud"

    def test_determine_specialization_fullstack(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Full Stack Engineer"
        assert sync_service._determine_specialization(job) == "FullStack"

    def test_determine_specialization_general(self, sync_service):
        job = MagicMock(spec=JobDetails)
        job.title = "Software Manager"
        assert sync_service._determine_specialization(job) == "General"

    def test_load_analysis_success(self, sync_service):
        mock_data = {"score": 85, "reasoning": "Test", "matching_skills": ["Python"], "missing_skills": []}
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
                result = sync_service._load_analysis("123")
                assert result.score == 85
                assert result.matching_skills == ["Python"]

    def test_load_analysis_not_found(self, sync_service):
        with patch("pathlib.Path.exists", return_value=False):
            result = sync_service._load_analysis("123")
            assert result.score == 0
            assert "not been scored" in result.reasoning

    def test_sync_success(self, sync_service):
        sync_service._sync_jobs_and_companies = MagicMock()
        sync_service.sync()
        sync_service.vault_manager.ensure_folders_exist.assert_called_once()
        sync_service._sync_jobs_and_companies.assert_called_once()
        sync_service.dashboard_generator.generate.assert_called_once()

    @patch("pathlib.Path.glob")
    @patch("src.generator.sync_service.SyncService._load_analysis")
    @patch("src.generator.sync_service.SyncService._write_job_note")
    @patch("src.generator.sync_service.SyncService._write_company_note")
    def test_sync_jobs_and_companies(
        self, mock_write_company, mock_write_job, mock_load_analysis, mock_glob, sync_service
    ):
        # Mock glob to return some job files
        mock_file = MagicMock()
        mock_file.stem = "123"
        mock_glob.return_value = [mock_file]

        # Mock extractor to return a job
        mock_job = MagicMock(spec=JobDetails)
        mock_job.company = "TestCo"
        sync_service.extractor.get_cached_job.return_value = mock_job

        with patch("pathlib.Path.exists", return_value=True):
            sync_service._sync_jobs_and_companies()

        mock_write_job.assert_called_once()
        mock_write_company.assert_called_once_with("TestCo")
