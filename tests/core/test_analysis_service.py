from unittest.mock import MagicMock, patch

import pytest

from src.core.analysis_service import AnalysisService
from src.core.relevance_scorer import ScoringResult
from src.ingest.job_details_extractor import JobDetails


class TestAnalysisService:
    @pytest.fixture
    def mock_llm(self):
        return MagicMock()

    @pytest.fixture
    def analysis_service(self, mock_llm):
        with (
            patch("src.core.analysis_service.RelevanceScorer") as mock_scorer_cls,
            patch("src.core.analysis_service.GapAnalyzer") as mock_gap_analyzer_cls,
        ):
            service = AnalysisService(mock_llm)
            service.scorer = mock_scorer_cls.return_value
            service.gap_analyzer = mock_gap_analyzer_cls.return_value
            return service

    def test_score_job_success(self, analysis_service):
        job = MagicMock(spec=JobDetails)
        job.id = "123"
        mock_result = ScoringResult(score=90, matching_skills=["A"], missing_skills=["B"], reasoning="Good")
        analysis_service.scorer.score_job.return_value = mock_result

        with patch("builtins.open", MagicMock()):
            with patch("json.dump") as mock_dump:
                res = analysis_service.score_job(job, "Resume content")
                assert res == mock_result
                mock_dump.assert_called_once()

    def test_score_all_cached_jobs(self, analysis_service):
        with (
            patch("pathlib.Path.glob") as mock_glob,
            patch("src.ingest.job_details_extractor.JobDetailsExtractor.get_cached_job") as mock_get_job,
        ):
            mock_file = MagicMock()
            mock_file.stem = "123"
            mock_glob.return_value = [mock_file]

            mock_job = MagicMock(spec=JobDetails)
            mock_job.id = "123"
            mock_get_job.return_value = mock_job

            analysis_service.score_job = MagicMock()

            analysis_service.score_all_cached_jobs("Resume text")
            analysis_service.score_job.assert_called_once_with(mock_job, "Resume text")

    def test_run_gap_analysis(self, analysis_service):
        with patch("pathlib.Path.glob") as mock_glob:
            mock_file = MagicMock()
            mock_file.stem = "123_analysis"
            mock_glob.return_value = [mock_file]

            mock_data = {"score": 85, "matching_skills": [], "missing_skills": ["X"], "reasoning": "Y"}
            with patch("builtins.open", MagicMock()):
                with patch("json.load", return_value=mock_data):
                    analysis_service.run_gap_analysis(min_score=80)
                    analysis_service.gap_analyzer.analyze_gaps.assert_called_once()
