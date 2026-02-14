from unittest.mock import MagicMock

import pytest

from src.core.ai import LLMClient
from src.core.relevance_scorer import RelevanceScorer, ScoringResult
from src.ingest.job_details_extractor import JobDetails


class TestRelevanceScorer:
    @pytest.fixture
    def mock_llm(self):
        return MagicMock(spec=LLMClient)

    @pytest.fixture
    def scorer(self, mock_llm):
        return RelevanceScorer(mock_llm)

    @pytest.fixture
    def sample_job(self):
        return JobDetails(
            id="123",
            title="Python Developer",
            company="Tech Co",
            location="Remote",
            description="Looking for a Python dev with FastAPI experience.",
            posted_date="1d",
            seniority_level="Mid",
            employment_type="Full-time",
            job_function="Engineering",
            industries="Software",
            link="http://link",
        )

    def test_score_job_success(self, scorer, mock_llm, sample_job):
        """Test successful scoring with valid LLM response."""
        mock_llm.generate_json.return_value = {
            "score": 85,
            "matching_skills": ["Python", "FastAPI"],
            "missing_skills": ["AWS"],
            "reasoning": "Strong match for Python and FastAPI.",
        }

        result = scorer.score_job("I know Python and FastAPI very well.", sample_job)

        assert isinstance(result, ScoringResult)
        assert result.score == 85
        assert "Python" in result.matching_skills
        assert result.reasoning == "Strong match for Python and FastAPI."
        mock_llm.generate_json.assert_called_once()

    def test_score_job_llm_failure(self, scorer, mock_llm, sample_job):
        """Test behavior when LLM returns empty or fails."""
        mock_llm.generate_json.return_value = {}

        result = scorer.score_job("Resume text", sample_job)

        # Should return fallback result instead of None
        assert isinstance(result, ScoringResult)
        assert result.score == 0
        assert "Unable to analyze - LLM scoring failed" in result.missing_skills
        assert "Failed to score this job automatically" in result.reasoning

    def test_score_job_exception(self, scorer, mock_llm, sample_job):
        """Test behavior when LLM client raises an exception."""
        mock_llm.generate_json.side_effect = Exception("API Error")

        result = scorer.score_job("Resume text", sample_job)

        # Should return fallback result instead of None
        assert isinstance(result, ScoringResult)
        assert result.score == 0
        assert "Unable to analyze - LLM scoring failed" in result.missing_skills
