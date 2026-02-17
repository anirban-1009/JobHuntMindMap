import json
from unittest.mock import MagicMock, patch

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
        mock_job_data = {
            "id": "123",
            "analysis_data": json.dumps(
                {"score": 85, "reasoning": "Test", "matching_skills": ["Python"], "missing_skills": []}
            ),
        }
        result = sync_service._load_analysis(mock_job_data)
        assert result.score == 85
        assert result.matching_skills == ["Python"]

    def test_load_analysis_not_found(self, sync_service):
        mock_job_data = {"id": "123", "analysis_data": None}
        result = sync_service._load_analysis(mock_job_data)
        assert result.score == 0
        assert "not been scored" in result.reasoning

    def test_sync_success(self, sync_service):
        sync_service._sync_all = MagicMock()
        sync_service.sync()
        sync_service.vault_manager.ensure_folders_exist.assert_called_once()
        sync_service._sync_all.assert_called_once()
        sync_service.dashboard_generator.generate.assert_called_once()

    def test_sync_all(self, sync_service):
        # Mock database to return some job rows
        mock_db = MagicMock()
        sync_service.extractor.db = mock_db
        sync_service.extractor.db.get_all_jobs.return_value = [{"id": "123", "analysis_data": None}]

        # Mock extractor to return a job
        mock_job = MagicMock(spec=JobDetails)
        mock_job.id = "123"
        mock_job.title = "SDE"
        mock_job.company = "TestCo"
        mock_job.description = "Test Description"
        sync_service.extractor.get_cached_job.return_value = mock_job

        # Mock NetworkGraphBuilder
        with patch("src.generator.sync_service.NetworkGraphBuilder") as mock_builder_class:
            mock_builder = mock_builder_class.return_value
            mock_person = MagicMock()
            mock_person.full_name = "John Doe"
            mock_person.company = "TestCo"
            mock_person.position = "Manager"
            mock_builder.connections = [mock_person]

            # Mock template manager return values
            sync_service.template_manager.render_person.return_value = "person content"
            sync_service.template_manager.render_job.return_value = "job content"
            sync_service.template_manager.render_company.return_value = "company content"

            sync_service._sync_all()

        # Check if files were written
        from unittest.mock import ANY

        sync_service.vault_manager.write_file.assert_any_call("person content", "John Doe.md", "people")
        sync_service.vault_manager.write_file.assert_any_call("job content", "SDE - TestCo.md", "jobs", subfolder=ANY)
        sync_service.vault_manager.write_file.assert_any_call("company content", "TestCo.md", "companies")
