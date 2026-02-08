import json
from unittest.mock import MagicMock, patch

import pytest

from src.ingest.job_details_extractor import JobDetails, JobDetailsExtractor
from src.ingest.selectors import (
    JOB_COMPANY_SELECTORS,
    JOB_DESCRIPTION_SELECTORS,
    JOB_INSIGHT_SELECTORS,
    JOB_TITLE_SELECTORS,
)


class TestJobDetailsExtractor:
    @pytest.fixture
    def mock_browser_manager(self):
        return MagicMock()

    @pytest.fixture
    def mock_llm(self):
        llm = MagicMock()
        llm.generate_json.return_value = None
        return llm

    @pytest.fixture
    def extractor(self, mock_browser_manager, mock_llm, tmp_path):
        return JobDetailsExtractor(mock_browser_manager, llm_client=mock_llm, cache_dir=tmp_path)

    def test_get_cached_job_exists(self, extractor, tmp_path):
        """Test loading job from cache when it exists."""
        job_id = "123"
        job_data = {
            "id": job_id,
            "title": "Dev",
            "company": "Tech",
            "location": "Remote",
            "description": "Desc",
            "posted_date": "2d",
            "seniority_level": "Mid",
            "employment_type": "Full",
            "job_function": "Eng",
            "industries": "IT",
            "link": "url",
            "salary": "$100k",
            "apply_link": "https://apply.com",
            "raw_data": None,
        }
        cache_file = tmp_path / f"{job_id}.json"
        with open(cache_file, "w") as f:
            json.dump(job_data, f)

        job = extractor.get_cached_job(job_id)
        assert job is not None
        assert job.id == job_id
        assert job.title == "Dev"

    def test_get_cached_job_not_exists(self, extractor):
        """Test returning None when job is not in cache."""
        assert extractor.get_cached_job("999") is None

    def test_extract_job_details_from_cache(self, extractor, mock_browser_manager):
        """Test that extract_job_details prefers cache over browser."""
        job_id = "123"
        with patch.object(extractor, "get_cached_job") as mock_get:
            mock_get.return_value = JobDetails(
                id=job_id,
                title="Cached",
                company="",
                location="",
                description="",
                posted_date="",
                seniority_level="",
                employment_type="",
                job_function="",
                industries="",
                link="",
                salary="",
                apply_link="",
            )

            result = extractor.extract_job_details(job_id, "some-url")

            assert result.title == "Cached"
            mock_browser_manager.goto.assert_not_called()

    def test_extract_job_details_success(self, extractor, mock_browser_manager):
        """Test successful extraction from mocked page."""
        job_id = "456"
        job_url = "https://linkedin.com/jobs/view/456"
        mock_page = mock_browser_manager.page

        # Mock selectors using the first selector in each list to match implementation
        def mock_locator(selector):
            mock_elem = MagicMock()
            if selector == JOB_TITLE_SELECTORS[0]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Software Engineer"
            elif selector == JOB_COMPANY_SELECTORS[0]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Google"
            elif selector == JOB_DESCRIPTION_SELECTORS[0]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Detailed description"
            elif selector == JOB_INSIGHT_SELECTORS[0]:
                mock_elem.count.return_value = 2
                item1 = MagicMock()
                item1.inner_text.return_value = "Full-time · IT"
                item2 = MagicMock()
                item2.inner_text.return_value = "Mid-Senior level · Software"
                mock_elem.all.return_value = [item1, item2]
            else:
                mock_elem.count.return_value = 0

            mock_elem.first = mock_elem
            return mock_elem

        mock_page.locator.side_effect = mock_locator

        result = extractor.extract_job_details(job_id, job_url)

        assert result is not None
        assert result.title == "Software Engineer"
        assert result.company == "Google"
        assert result.description == "Detailed description"
        assert result.employment_type == "Full-time"
        assert result.seniority_level == "Mid-Senior level"

        # Verify cache file created
        cache_path = extractor.cache_dir / f"{job_id}.json"
        assert cache_path.exists()

    def test_extract_job_details_failure(self, extractor, mock_browser_manager):
        """Test behavior when extraction fails (e.g. timeout)."""
        job_id = "fail"
        mock_browser_manager.goto.side_effect = Exception("Page load error")

        result = extractor.extract_job_details(job_id, "url")
        assert result is None

    def test_selector_fallback(self, extractor, mock_browser_manager):
        """Test that extractor falls back to secondary selectors if primary fails."""
        job_id = "fallback-selector"
        mock_page = mock_browser_manager.page

        # Setup: First title selector fails (count 0), second succeeds
        def mock_locator(selector):
            mock_elem = MagicMock()
            if selector == JOB_TITLE_SELECTORS[0]:
                mock_elem.count.return_value = 0
            elif selector == JOB_TITLE_SELECTORS[1]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Fallback Title"
                mock_elem.first = mock_elem
            elif selector == JOB_COMPANY_SELECTORS[0]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Company"
                mock_elem.first = mock_elem
            else:
                mock_elem.count.return_value = 0
            return mock_elem

        mock_page.locator.side_effect = mock_locator

        result = extractor.extract_job_details(job_id, "url")
        assert result.title == "Fallback Title"

    def test_ai_fallback_extraction(self, extractor, mock_browser_manager, mock_llm):
        """Test that extractor uses LLM when selector extraction is insufficient."""
        job_id = "ai-fallback"
        mock_page = mock_browser_manager.page

        # Setup: Selectors return minimal info (missing description)
        def mock_locator(selector):
            mock_elem = MagicMock()
            if selector == JOB_TITLE_SELECTORS[0]:
                mock_elem.count.return_value = 1
                mock_elem.inner_text.return_value = "Basic Title"
                mock_elem.first = mock_elem
            # Return cached/empty for others to trigger AI fallback
            mock_elem.count.return_value = 0
            if selector == "body":
                mock_elem.inner_text.return_value = "Raw page text containing job details..."
                return mock_elem
            return mock_elem

        mock_page.locator.side_effect = mock_locator

        # Setup LLM to return enhanced details
        mock_llm.generate_json.return_value = {
            "title": "Enhanced Title",
            "company": "AI Company",
            "description": "Full description extracted by AI",
            "location": "AI Land",
        }

        result = extractor.extract_job_details(job_id, "url")

        # Verify LLM was called
        mock_llm.generate_json.assert_called_once()

        # Verify result contains AI-extracted data
        assert result.title == "Enhanced Title"
        assert result.company == "AI Company"
        assert result.description == "Full description extracted by AI"
