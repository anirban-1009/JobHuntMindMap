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

    def test_determine_specialization_ai_ml(self):
        job = JobDetails(
            id="1",
            title="Senior Machine Learning Engineer (AI/NLP)",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "AI_ML"

        job.title = "LLM Researcher"
        assert job.determine_specialization() == "AI_ML"

    def test_determine_specialization_python(self):
        job = JobDetails(
            id="1",
            title="Django Backend Developer",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "Python_Dev"

    def test_determine_specialization_backend(self):
        job = JobDetails(
            id="1",
            title="Platform Engineer (API)",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "Backend"

    def test_determine_specialization_frontend(self):
        job = JobDetails(
            id="1",
            title="React Web Developer",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "Frontend"

    def test_determine_specialization_devops(self):
        job = JobDetails(
            id="1",
            title="Kubernetes Infrastructure Specialist",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "DevOps_Cloud"

    def test_determine_specialization_fullstack(self):
        job = JobDetails(
            id="1",
            title="Full Stack Engineer",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "FullStack"

    def test_determine_specialization_general(self):
        job = JobDetails(
            id="1",
            title="Software Manager",
            company="A",
            location="B",
            description="C",
            posted_date="D",
            seniority_level="E",
            employment_type="F",
            job_function="G",
            industries="H",
            link="I",
        )
        assert job.determine_specialization() == "General"

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

    def test_prune_vault_protects_connections_csv(self, sync_service):
        """Verify that 'connections.csv' is never deleted by the prune command."""
        mock_db = MagicMock()
        sync_service.extractor.db = mock_db
        mock_db.get_all_jobs.return_value = []  # Everything should be pruned

        # Mock paths
        jobs_folder = MagicMock()
        companies_folder = MagicMock()
        people_folder = MagicMock()

        sync_service.vault_manager.vault_path = MagicMock()
        sync_service.vault_manager.folders = {"jobs": "Jobs", "companies": "Companies", "people": "People"}

        def mock_side_effect(path):
            if "Jobs" in str(path):
                return jobs_folder
            if "Companies" in str(path):
                return companies_folder
            if "People" in str(path):
                return people_folder
            return MagicMock()

        sync_service.vault_manager.vault_path.__truediv__.side_effect = mock_side_effect
        jobs_folder.exists.return_value = True
        companies_folder.exists.return_value = True
        people_folder.exists.return_value = True

        # Create mock files including connections.csv
        file_jobs = MagicMock()
        file_jobs.name = "Job1.md"
        file_jobs.read_text.return_value = "- **Job ID:** 999"

        file_conn = MagicMock()
        file_conn.name = "connections.csv"
        file_conn.suffix = ".csv"

        jobs_folder.rglob.return_value = [file_jobs, file_conn]
        companies_folder.glob.return_value = [file_conn]

        sync_service.prune_vault()

        # file_jobs should be unlinked (deleted) because ID 999 is not in []
        file_jobs.unlink.assert_called_once()
        # file_conn should NOT be unlinked
        file_conn.unlink.assert_not_called()
