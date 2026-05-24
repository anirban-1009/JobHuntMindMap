import json
import random
import time
from typing import Dict, List

from src.core.ai import LLMClient
from src.ingest.browser_manager import BrowserManager
from src.ingest.job_searcher import JobSearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExternalSiteSearcher:
    """Searches external company career sites for job postings."""

    def __init__(self, browser_manager: BrowserManager, llm_client: LLMClient) -> None:
        """Initialize the ExternalSiteSearcher.

        Args:
            browser_manager: Initialized BrowserManager instance.
            llm_client: LLMClient to parse the career site.
        """
        self.browser = browser_manager
        self.llm = llm_client

    def search_site(self, url: str, company_name: str = "Unknown") -> List[JobSearchResult]:
        """Visits an external career site and extracts job postings using LLM.

        Args:
            url: The URL of the company career page.
            company_name: Optional company name.

        Returns:
            A list of JobSearchResult objects representing job postings.
        """
        logger.info(f"Searching external career site: {url}")
        results: List[JobSearchResult] = []
        try:
            self.browser.goto(url)
            time.sleep(random.uniform(3.0, 6.0))
            page = self.browser.page

            # Scroll multiple times to trigger lazy loading
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.0)

            # Wait additional time for final elements to load
            time.sleep(2.0)

            # Extract all promising links from the page
            links_data = page.evaluate(
                r"""
                () => {
                    return Array.from(document.querySelectorAll('a')).map(a => ({
                        text: a.innerText.trim(),
                        href: a.href
                    })).filter(a => a.text.length > 2 && a.href.startsWith('http') && !a.href.includes('#'));
                }
            """
            )

            unique_links: Dict[str, str] = {}
            for item in links_data:
                href: str = item["href"]
                text: str = item["text"]
                if href not in unique_links:
                    unique_links[href] = text

            logger.info(f"Extracted {len(links_data)} total links, {len(unique_links)} unique")

            # Only select the first 80 unique links to avoid overloading the LLM context
            filtered_links = [{"text": v, "href": k} for k, v in unique_links.items()][:80]

            if not filtered_links:
                logger.warning(f"No valid links found on {url}")
                if links_data:
                    logger.debug(f"First 5 raw links were: {links_data[:5]}")
                return []

            logger.info(f"Sending {len(filtered_links)} links to LLM for classification.")

            prompt = (
                "Identify which of the following links are specific job postings (not generic career pages, "
                "login pages, privacy policies, or about pages). "
                "Return a JSON list of objects with 'title' (extracted or cleaned from the link text) "
                "and 'url' (the exact href). Only include actual job postings. If none, return [].\n\n"
                f"Links:\n{json.dumps(filtered_links, indent=2)}"
            )

            extracted = self.llm.generate_json(prompt)
            if isinstance(extracted, list):
                for item in extracted:
                    job_url: str = item.get("url", "")
                    title: str = item.get("title", "")
                    if job_url and title:
                        # Create a deterministic ID from the URL hash
                        job_id = f"ext-{abs(hash(job_url))}"
                        results.append(
                            JobSearchResult(
                                id=job_id,
                                title=title,
                                company=company_name,
                                link=job_url,
                                location="Unknown",
                            )
                        )

            logger.info(f"LLM identified {len(results)} job postings on {url}")
            return results

        except Exception as e:
            logger.error(f"Failed to search external site {url}: {e}")
            return []
