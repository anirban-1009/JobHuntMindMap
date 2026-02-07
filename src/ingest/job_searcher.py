import urllib.parse
from dataclasses import dataclass
from typing import Dict, List

from src.core.constants import LINKEDIN_JOBS_SEARCH_URL, ExperienceLevel, JobType, LocationType
from src.ingest.browser_manager import BrowserManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobSearchResult:
    """Represents a job listing from search results."""

    id: str
    title: str
    company: str
    link: str
    location: str


class JobSearcher:
    """Constructs search URLs and scrapes LinkedIn job listings."""

    def __init__(self, browser_manager: BrowserManager):
        """
        Initialize the JobSearcher.

        Args:
            browser_manager: Initialized BrowserManager instance.
        """
        self.browser = browser_manager

    def construct_search_url(
        self, keywords: str, location: str, filters: Dict[str, List[str]] = None, location_type: str = "Any"
    ) -> str:
        """
        Constructs a LinkedIn search URL based on criteria.

        Args:
            keywords: Search keywords (e.g., "Python Developer").
            location: Search location (e.g., "United States").
            filters: Optional dictionary of filters (experience_level, job_type).
            location_type: On-site, Remote, Hybrid, or Any.

        Returns:
            A fully qualified LinkedIn search URL.
        """
        params = {
            "keywords": keywords,
            "location": location,
            "refresh": "true",
        }

        # Handle Location Type (f_WT)
        loc_val = LocationType.from_str(location_type)
        if loc_val:
            params["f_WT"] = loc_val

        # Handle Experience Level (f_E)
        if filters and "experience_level" in filters:
            levels = [ExperienceLevel.from_str(lvl) for lvl in filters["experience_level"]]
            levels = [v for v in levels if v]
            if levels:
                params["f_E"] = ",".join(levels)

        # Handle Job Type (f_JT)
        if filters and "job_type" in filters:
            types = [JobType.from_str(jt) for jt in filters["job_type"]]
            types = [v for v in types if v]
            if types:
                params["f_JT"] = ",".join(types)

        query_string = urllib.parse.urlencode(params)
        return f"{LINKEDIN_JOBS_SEARCH_URL}?{query_string}"

    def search(
        self, keywords: str, location: str, filters: Dict[str, List[str]] = None, location_type: str = "Any"
    ) -> List[JobSearchResult]:
        """
        Performs the job search and scrapes results.

        Args:
            keywords: Search keywords.
            location: Search location.
            filters: Optional filters.
            location_type: On-site, Remote, Hybrid, or Any.

        Returns:
            A list of JobSearchResult objects.
        """
        url = self.construct_search_url(keywords, location, filters, location_type)
        logger.info(f"Searching for jobs: {url}")

        self.browser.goto(url)
        page = self.browser.page

        # LinkedIn might show a login wall if cookies are not set or expired.
        # BrowserManager should handle state, but we should check if we are on the right page.
        if "login" in page.url:
            logger.error("LinkedIn login wall detected. Please ensure session.json is valid.")
            return []

        # Wait for job cards to load
        try:
            page.wait_for_selector(".jobs-search-results-list", timeout=10000)
        except Exception:
            logger.warning("Job results list not found. Maybe no results or different layout.")
            # Check for "No matching jobs found"
            if "No matching jobs found" in page.content():
                logger.info("No matching jobs found.")
            return []

        # Scroll to load more if needed (LinkedIn often loads more on scroll)
        # For now, let's just get what's visible.

        job_cards = page.locator(".jobs-search-results-list__item").all()
        results = []

        for card in job_cards:
            try:
                # Extract details
                # Note: Selectors can be very brittle.
                title_elem = card.locator(".job-card-list__title")
                company_elem = card.locator(".job-card-container__primary-description")
                location_elem = card.locator(".job-card-container__metadata-item")

                if title_elem.count() == 0:
                    continue

                title = title_elem.inner_text().strip()
                link = title_elem.get_attribute("href")
                # Normalize link (remove query params)
                if link:
                    link = link.split("?")[0]
                    # LinkedIn links can be relative
                    if link.startswith("/"):
                        link = f"https://www.linkedin.com{link}"

                # Extract Job ID from link (usually /jobs/view/123456789/)
                job_id = ""
                if link:
                    parts = link.rstrip("/").split("/")
                    if parts:
                        job_id = parts[-1]

                company = company_elem.inner_text().strip() if company_elem.count() > 0 else "Unknown"
                location_str = location_elem.first.inner_text().strip() if location_elem.count() > 0 else ""

                results.append(
                    JobSearchResult(id=job_id, title=title, company=company, link=link or "", location=location_str)
                )
            except Exception as e:
                logger.debug(f"Failed to parse job card: {e}")
                continue

        logger.info(f"Found {len(results)} jobs.")
        return results
