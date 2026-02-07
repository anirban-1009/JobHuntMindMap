import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingest.browser_manager import BrowserManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JobDetails:
    """Represents full details of a job listing."""

    id: str
    title: str
    company: str
    location: str
    description: str
    posted_date: str
    seniority_level: str
    employment_type: str
    job_function: str
    industries: str
    link: str
    raw_data: Optional[Dict[str, Any]] = None


class JobDetailsExtractor:
    """Visits individual job URLs and extracts full details."""

    def __init__(self, browser_manager: BrowserManager, cache_dir: Optional[Path] = None):
        """
        Initialize the JobDetailsExtractor.

        Args:
            browser_manager: Initialized BrowserManager instance.
            cache_dir: Directory to store cached job details. Defaults to data/job_cache.
        """
        self.browser = browser_manager
        self.cache_dir = cache_dir or Path("data/job_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, job_id: str) -> Path:
        """Returns the path to the cached job file."""
        return self.cache_dir / f"{job_id}.json"

    def get_cached_job(self, job_id: str) -> Optional[JobDetails]:
        """Loads job details from cache if they exist."""
        cache_path = self._get_cache_path(job_id)
        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return JobDetails(**data)
            except Exception as e:
                logger.warning(f"Failed to load cache for job {job_id}: {e}")
        return None

    def _save_to_cache(self, job: JobDetails):
        """Saves job details to cache."""
        cache_path = self._get_cache_path(job.id)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(asdict(job), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save job {job.id} to cache: {e}")

    def extract_job_details(self, job_id: str, job_url: str) -> Optional[JobDetails]:
        """
        Visits a job URL and extracts its details.

        Args:
            job_id: The unique ID of the job.
            job_url: The full URL to the job listing.

        Returns:
            JobDetails object if successful, None otherwise.
        """
        # Check cache first
        cached = self.get_cached_job(job_id)
        if cached:
            logger.info(f"Using cached details for job {job_id}")
            return cached

        logger.info(f"Extracting details for job {job_id}: {job_url}")
        try:
            self.browser.goto(job_url)
        except Exception as e:
            logger.error(f"Failed to navigate to {job_url}: {e}")
            return None

        page = self.browser.page

        try:
            # Wait for any of the main job page elements to appear
            wait_selectors = [
                ".jobs-description",
                ".top-card-layout",
                ".main-content",
                ".description__text",
                ".job-details-jobs-unified-top-card",
            ]
            try:
                page.wait_for_selector(", ".join(wait_selectors), timeout=15000)
            except Exception:
                logger.warning(f"Wait for job details timed out for {job_id}. Current URL: {page.url}")

            # Check for login walls
            if page.locator(".modal--contextual-sign-in, .authwall-modal, .sign-in-modal").count() > 0:
                logger.debug(f"Login modal detected on job page {job_id}. Attempting to extract what's visible.")

            # Let's try to be smart about extracting them.
            title = self._get_text(
                page,
                [
                    ".job-details-jobs-unified-top-card__job-title",
                    ".top-card-layout__title",
                    ".jobs-unified-top-card__job-title",
                    "h1.top-card-layout__title",
                    "h1",
                    ".topcard__title",
                    "h2.top-card-layout__title",
                ],
            )

            company = self._get_text(
                page,
                [
                    ".job-details-jobs-unified-top-card__company-name",
                    ".topcard__org-name-link",
                    ".topcard__flavor a",
                    ".top-card-layout__first-subline a",
                    ".job-details-jobs-unified-top-card__company-name a",
                    ".jobs-unified-top-card__company-name",
                    ".app-shared-outline--company-name",
                ],
            )

            location = self._get_text(
                page,
                [
                    ".job-details-jobs-unified-top-card__bullet",
                    ".topcard__flavor--bullet",
                    ".top-card-layout__first-subline span:nth-child(2)",
                    ".jobs-unified-top-card__bullet",
                    ".job-details-jobs-unified-top-card__primary-description-container span:last-child",
                ],
            )

            description = self._get_text(
                page,
                [
                    ".jobs-description__container",
                    ".show-more-less-html__markup",
                    ".description__text",
                    ".jobs-description-content__text",
                    ".description__text--rich",
                    "#job-details",
                ],
            )

            posted_date = self._get_text(
                page,
                [
                    ".job-details-jobs-unified-top-card__posted-date",
                    ".topcard__flavor--metadata",
                    "span.posted-time-ago__text",
                    ".topcard__flavor--metadata.posted-time-ago__text",
                ],
            )

            # Metadata extraction
            seniority = ""
            employment_type = ""
            job_function = ""
            industries = ""

            # Try to extract from job insights (unified view)
            insights = page.locator(".job-details-jobs-unified-top-card__job-insight").all()
            for item in insights:
                text = item.inner_text()
                if any(x in text for x in ["Full-time", "Contract", "Part-time", "Temporary"]):
                    employment_type = text.split("·")[0].strip() if "·" in text else text.strip()
                if any(
                    x in text
                    for x in ["Entry level", "Mid-Senior level", "Associate", "Director", "Executive", "Internship"]
                ):
                    seniority = text.split("·")[0].strip() if "·" in text else text.strip()

            # Try to extract from job criteria list (direct view)
            criteria_items = page.locator(".description__job-criteria-item").all()
            for item in criteria_items:
                header = self._get_text(item, [".description__job-criteria-subheader"])
                value = self._get_text(item, [".description__job-criteria-text"])

                if "Seniority level" in header:
                    seniority = value
                elif "Employment type" in header:
                    employment_type = value
                elif "Job function" in header:
                    job_function = value
                elif "Industries" in header:
                    industries = value

            job_details = JobDetails(
                id=job_id,
                title=title,
                company=company,
                location=location,
                description=description,
                posted_date=posted_date,
                seniority_level=seniority,
                employment_type=employment_type,
                job_function=job_function,
                industries=industries,
                link=job_url,
            )

            if job_details.title or job_details.description:
                self._save_to_cache(job_details)
                return job_details
            else:
                logger.warning(f"Extracted empty details for job {job_id}")
                return None

        except Exception as e:
            logger.error(f"Error during job extraction for {job_id}: {e}")
            return None

    def _get_text(self, root: Any, selectors: List[str]) -> str:
        """Helper to try multiple selectors and return the first found text."""
        for selector in selectors:
            try:
                elem = root.locator(selector)
                if elem.count() > 0:
                    return elem.first.inner_text().strip()
            except Exception:
                continue
        return ""

    def extract_multiple_jobs(self, job_list: List[Any], delay: float = 2.0) -> List[JobDetails]:
        """
        Extracts details for multiple jobs.

        Args:
            job_list: List of objects/dicts with 'id' and 'link'.
            delay: Delay in seconds between requests.

        Returns:
            List of JobDetails.
        """
        results = []
        for job in job_list:
            jid = getattr(job, "id", None) or job.get("id")
            jlink = getattr(job, "link", None) or job.get("link")

            if not jid or not jlink:
                continue

            details = self.extract_job_details(jid, jlink)
            if details:
                results.append(details)

            if delay > 0:
                time.sleep(delay)

        return results
