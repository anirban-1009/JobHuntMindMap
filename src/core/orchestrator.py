import json
import pathlib
import sys
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import yaml
from colorama import Fore

from src.core.ai import get_llm_client
from src.core.analysis_service import AnalysisService
from src.core.referral_service import ReferralService
from src.core.relevance_scorer import FastScorer
from src.core.resume_service import ResumeService
from src.generator.resume_tailorer import ResumeTailorer
from src.generator.sync_service import SyncService
from src.ingest.browser_manager import BrowserManager
from src.ingest.job_details_extractor import JobDetailsExtractor
from src.ingest.job_searcher import JobSearcher
from src.ingest.resume_parser import PDFResumeParser
from src.notification.email_service import EmailService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MindMapApp:
    """Orchestrates services for the Job Hunt Mindmap application."""

    def __init__(self, config_path: str) -> None:
        """Initialize services and load configuration."""
        self.project_root = pathlib.Path(__file__).parents[2]
        self.config_path = pathlib.Path(config_path)

        self.config = self._load_config()
        self.session_path = self.project_root / "data" / "session.json"
        self.llm = get_llm_client(self.config.get("ai", {}))

        # Service Initialization
        self.resume_service = ResumeService(self.llm, resume_path=self.config.get("user", {}).get("resume_path"))
        self.analysis_service = AnalysisService(self.llm)
        self.referral_service = ReferralService(self.llm, self.config)

    def _load_config(self) -> Dict[str, Any]:
        """Load and parse the YAML configuration file."""
        if not self.config_path.exists():
            print(f"{Fore.RED}Config file not found: {self.config_path}")
            sys.exit(1)
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            try:
                return yaml.safe_load(config_file)
            except yaml.YAMLError as error:
                print(f"{Fore.RED}Error parsing YAML: {error}")
                sys.exit(1)

    def check_env(self) -> None:
        """Check if the environment and configuration are valid."""
        print(f"{Fore.CYAN}Checking environment...")
        print(f"{Fore.GREEN}Config file valid.")
        print(f"{Fore.GREEN}Mindmap is ready to run!")

    def login(self) -> None:
        """Launch browser for manual platform authentication."""
        print(f"{Fore.CYAN}Starting browser for manual login...")
        try:
            with BrowserManager(headless=False, session_path=self.session_path) as browser:
                browser.login_manual()
        except Exception as error:
            print(f"{Fore.RED}Login failed: {error}")
            sys.exit(1)

    def _get_locations(self) -> List[str]:
        """Get flattened list of target locations from config."""
        loc_cfg = self.config.get("search", {}).get("location", "United States")
        if isinstance(loc_cfg, str):
            return [location.strip() for location in loc_cfg.split(",") if location.strip()]
        return loc_cfg

    def search(self, headless: bool) -> None:
        """Search for new job postings across defined keywords/locations."""
        print(f"{Fore.CYAN}Starting job search (headless={headless})...")
        try:
            with BrowserManager(headless=headless, session_path=self.session_path) as browser:
                searcher = JobSearcher(browser)
                search_cfg = self.config.get("search", {})
                all_results = []
                for keywords in search_cfg.get("keywords", []):
                    for loc in self._get_locations():
                        print(f"Searching for '{keywords}' in {loc}...")
                        results = searcher.search(
                            keywords, loc, search_cfg.get("filters", {}), search_cfg.get("location_type", "Any")
                        )
                        all_results.extend(results)

                unique = {job.id: job for job in all_results if job.id}.values()
                filtered = self._filter_jobs(list(unique))

                print(f"{Fore.CYAN}\nTotal unique jobs found: {len(filtered)} (after filtering)")

            # Save search results to DB as discovery cache
            extractor = JobDetailsExtractor(browser, llm_client=self.llm)
            for job in filtered:
                # We save minimal info; status 'discovered' means JD not yet scraped
                extractor.db.save_job(
                    {
                        "id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "link": job.link,
                        "status": "discovered",
                    }
                )

            for job in filtered[:10]:
                print(f"- {Fore.WHITE}{job.title} {Fore.YELLOW}@ {job.company}")
        except Exception as error:
            print(f"{Fore.RED}Search failed: {error}")
            sys.exit(1)

    def scrape(
        self,
        headless: bool,
        limit: Optional[int],
        force: bool,
        min_fast_score: int = 0,
        do_score: bool = False,
        job_id: Optional[str] = None,
    ) -> None:
        """Extract full details for found jobs and cache them."""
        print(f"{Fore.CYAN}Starting extraction (headless={headless})...")
        try:
            with BrowserManager(headless=headless, session_path=self.session_path) as browser:
                searcher = JobSearcher(browser)
                extractor = JobDetailsExtractor(browser, llm_client=self.llm)

                if job_id:
                    # Specific job requested
                    logger.info(f"Scraping specific job ID: {job_id}")
                    # Create a dummy object with ID and Link so extractor can process it
                    # We assume standard LinkedIn URL format
                    dummy_link = f"https://www.linkedin.com/jobs/view/{job_id}/"
                    dummy_job = SimpleNamespace(id=job_id, link=dummy_link, title=f"Job {job_id}")
                    filtered = [dummy_job]
                else:
                    # Run full search
                    all_found = []
                    cfg = self.config.get("search", {})
                    seen_searches = set()

                    for kw in cfg.get("keywords", []):
                        for loc in self._get_locations():
                            search_key = f"{kw}|{loc}"
                            if search_key in seen_searches:
                                continue

                            results = searcher.search(kw, loc, cfg.get("filters", {}), cfg.get("location_type", "Any"))
                            all_found.extend(results)
                            seen_searches.add(search_key)

                            # Optimization: if we found many jobs in this location for this keyword,
                            # maybe we don't need to search sub-locations?
                            # (Optional: stop after first location if results > 15)
                            if len(results) >= 15:
                                logger.debug(
                                    f"Found {len(results)} jobs for '{kw}' in '{loc}', skipping other locations for this keyword."
                                )
                                break

                    unique = list({job.id: job for job in all_found if job.id}.values())
                    filtered = self._filter_jobs(unique)

                # Add previously discovered jobs from DB that haven't been scraped yet
                discovered_jobs = extractor.db.get_jobs_by_status("discovered")
                if discovered_jobs:
                    logger.info(f"Adding {len(discovered_jobs)} previously discovered jobs from cache.")
                    for dj in discovered_jobs:
                        if dj["id"] not in {j.id for j in filtered}:
                            # Convert DB dict to object compatible with extractor
                            filtered.append(
                                SimpleNamespace(
                                    id=dj["id"],
                                    title=dj["title"],
                                    company=dj["company"],
                                    location=dj["location"],
                                    link=dj["link"],
                                )
                            )

                # Fast Scoring (skip if specific job requested as we don't have details yet)
                if not job_id:
                    resume_data = self.resume_service.get_resume_data()
                    skills = []
                    if isinstance(resume_data.get("skills"), dict):
                        for cat_skills in resume_data["skills"].values():
                            if isinstance(cat_skills, list):
                                skills.extend(cat_skills)

                    fast_scorer = FastScorer(skills)
                    scored_jobs = []
                    for job in filtered:
                        f_score = fast_scorer.score_result(job)
                        if f_score >= min_fast_score:
                            scored_jobs.append((f_score, job))

                    # Sort by score descending
                    scored_jobs.sort(key=lambda x: x[0], reverse=True)
                    final_jobs = [j[1] for j in scored_jobs]
                else:
                    final_jobs = filtered
                if limit:
                    final_jobs = final_jobs[:limit]

                if not final_jobs:
                    print(f"{Fore.YELLOW}No jobs met the minimum fast score of {min_fast_score}.")
                    return

                print(f"{Fore.CYAN}Extracting details for {len(final_jobs)} prioritized jobs...")
                # Only pass force to extraction, scoring handles its own force
                details = extractor.extract_multiple_jobs(final_jobs, force=force)
                print(f"{Fore.GREEN}Scraped {len(details)} / {len(final_jobs)} jobs.")

                if do_score and details:
                    print(f"{Fore.CYAN}Performing LLM scoring on scraped jobs...")
                    resume_path = pathlib.Path(self.config.get("user", {}).get("resume_path", "data/resume.pdf"))
                    resume_text = PDFResumeParser().extract_text(resume_path)
                    for job in details:
                        # Skip if already scored, unless force is used
                        res = self.analysis_service.score_job(job, resume_text, force=force)
                        if res:
                            color = Fore.GREEN if res.score >= 70 else Fore.YELLOW
                            print(f"[{job.id}] {color}Score {res.score}{Fore.RESET} - {job.title} @ {job.company}")

        except Exception as error:
            print(f"{Fore.RED}Scrape failed: {error}")
            sys.exit(1)

    def refresh_existing_jobs(
        self, headless: bool, limit: Optional[int], do_score: bool = False, unknown_only: bool = False
    ) -> None:
        """Re-scrape details for jobs already present in the database."""
        print(f"{Fore.CYAN}Refreshing existing records (headless={headless})...")
        try:
            extractor = JobDetailsExtractor(None)
            if not extractor.db:
                print(f"{Fore.RED}Database not available.")
                return

            all_jobs = extractor.db.get_all_jobs(limit=1000)
            if not all_jobs:
                print(f"{Fore.YELLOW}No jobs found in database to refresh.")
                return

            if unknown_only:
                all_jobs = [
                    j
                    for j in all_jobs
                    if "Unknown" in j.get("title")
                    or "Unknown" in j.get("company")
                    or not j.get("title")
                    or not j.get("company")
                ]
                if not all_jobs:
                    print(f"{Fore.YELLOW}No unknown jobs found to refresh.")
                    return

            if limit:
                all_jobs = all_jobs[:limit]

            print(f"{Fore.WHITE}Found {len(all_jobs)} jobs to refresh.")

            with BrowserManager(headless=headless, session_path=self.session_path) as browser:
                extractor.browser = browser
                extractor.llm = self.llm

                details = extractor.extract_multiple_jobs(all_jobs, force=True)
                print(f"{Fore.GREEN}Successfully refreshed {len(details)} / {len(all_jobs)} jobs.")

                if do_score and details:
                    print(f"{Fore.CYAN}Performing LLM re-scoring...")
                    resume_path = pathlib.Path(self.config.get("user", {}).get("resume_path", "data/resume.pdf"))
                    resume_text = PDFResumeParser().extract_text(resume_path)
                    for job in details:
                        self.analysis_service.score_job(job, resume_text)
        except Exception as error:
            print(f"{Fore.RED}Refresh failed: {error}")
            sys.exit(1)

    def score_jobs(self, score_all: bool, job_id: Optional[str]) -> None:
        """Analyze job requirements against resume and assign scores."""
        try:
            resume_path = pathlib.Path(self.config.get("user", {}).get("resume_path", "data/resume.pdf"))
            resume_text = PDFResumeParser().extract_text(resume_path)

            if job_id:
                job = JobDetailsExtractor(None).get_cached_job(job_id)
                if job:
                    res = self.analysis_service.score_job(job, resume_text)
                    if res:
                        color = Fore.GREEN if res.score >= 70 else Fore.YELLOW
                        print(f"Job {job_id}: {color}Score {res.score}{Fore.RESET} - {res.reasoning}")
            elif score_all:
                self.analysis_service.score_all_cached_jobs(resume_text)
        except Exception as error:
            print(f"{Fore.RED}Scoring failed: {error}")
            sys.exit(1)

    def analyze_gaps(self, min_score: int, tag: Optional[str] = None) -> None:
        """Identify missing skills across highly-rated job postings."""
        filter_msg = f" (tag: {tag})" if tag else ""
        print(f"{Fore.CYAN}Analyzing gaps across jobs scored >= {min_score}{filter_msg}...")
        report = self.analysis_service.run_gap_analysis(min_score, tag=tag)
        if report:
            print(f"{Fore.GREEN}\n=== Top Missing Skills ===")
            for skill, count in report.skill_frequency.items():
                print(f"- {skill}: {count} jobs")
            print(f"{Fore.CYAN}\n=== Improvement Plan ===\n{report.improvement_plan}")

            # Also Sync to Obsidian
            from src.generator.sync_service import SyncService

            sync = SyncService(self.config)
            content = sync.template_manager.render_gap_analysis(report, min_score, tag)
            filename = f"Gap Analysis - {tag if tag else 'All'}.md"
            file_path = sync.vault_manager.write_file(content, filename, "analysis")
            print(f"{Fore.GREEN}\nGap analysis report saved to Obsidian: {file_path}")
        else:
            print(f"{Fore.YELLOW}No jobs found with a score of {min_score} or higher{filter_msg}.")
            print(
                f"{Fore.WHITE}Try running '{Fore.CYAN}uv run mindmap score --all{Fore.WHITE}' first, or lowering the threshold."
            )

    def notify(self, min_score: int) -> None:
        """Send job digest emails for jobs meeting the score threshold."""
        print(f"{Fore.CYAN}Preparing notifications...")
        extractor = JobDetailsExtractor(None)
        if not extractor.db:
            return

        analyses = extractor.db.get_all_analyses(min_score=min_score)
        scored_jobs = []
        for row in analyses:
            try:
                data = json.loads(row["analysis_data"])
                job = extractor.get_cached_job(row["id"])
                if job:
                    scored_jobs.append({"job": job, "score": SimpleNamespace(**data)})
            except Exception as e:
                logger.warning(f"Failed to process analysis for {row['id']}: {e}")

        if scored_jobs:
            EmailService(self.config).send_job_digest(scored_jobs)
            print(f"{Fore.GREEN}Notifications sent.")

    def sync(self) -> None:
        """Export processed job data to external knowledge base."""
        print(f"{Fore.CYAN}Syncing to Obsidian...")
        SyncService(self.config).sync()
        print(f"{Fore.GREEN}Sync complete.")

    def sync_back(self) -> None:
        """Sync status and changes from Obsidian back to the database."""
        print(f"{Fore.CYAN}Syncing back from Obsidian...")
        SyncService(self.config).sync_from_obsidian()
        print(f"{Fore.GREEN}Sync-back complete.")

    def referral(self, job_id: str, connection_name: Optional[str], max_chars: int = 300) -> Optional[Dict[str, str]]:
        """Generate personalized referral message for a job and contact."""
        job = JobDetailsExtractor(None).get_cached_job(job_id)
        if not job:
            print(f"{Fore.RED}Job {job_id} not found.")
            return

        matches = self.referral_service.find_potential_connections(job)
        target = None
        if connection_name:
            target = SimpleNamespace(full_name=connection_name, position="Professional")
        elif matches:
            target = matches[0]
            print(f"{Fore.GREEN}Using existing connection: {target.full_name}")

        # Handled manual input in CLI side or here?
        # If we keep this class as the core, it might need to return a "needs_input" status
        # but for this specific tool, let's allow input in the Orchestrator for simplicity
        # if it's strictly a CLI tool.
        if not target:
            print(f"{Fore.YELLOW}No connections found.")
            return None  # Signal to CLI that it needs input

        resume_data = self.resume_service.get_resume_data()
        msg = self.referral_service.generate_message(job, target, resume_data, max_chars=max_chars)
        self.referral_service.save_referral(job_id, target.full_name, msg)
        return {"to": target.full_name, "message": msg}

    def tailor_resume(self, job_id: str) -> Optional[pathlib.Path]:
        """Create a job-optimized resume PDF based on JD analysis."""
        job = JobDetailsExtractor(None).get_cached_job(job_id)
        if not job:
            return None

        resume_data = self.resume_service.get_resume_data()
        tailorer = ResumeTailorer(self.config)

        print(f"{Fore.CYAN}Tailoring for {job.title} at {job.company}...")
        job_desc = f"Title: {job.title}\nCompany: {job.company}\n\n{job.description}"
        tailored_data = tailorer.tailor_resume(resume_data, job_desc)

        latex = tailorer.generate_latex(tailored_data)
        output_dir = pathlib.Path("output/resumes")
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_company = (
            "".join(char for char in job.company if char.isalnum() or char in (" ", "_", "-")).strip().replace(" ", "_")
        )
        output_path = output_dir / f"Resume_{safe_company}_{job_id}.pdf"

        tailorer.compile_pdf(latex, output_path)
        return output_path

    def test_ai(self, prompt: str) -> None:
        """Test AI client connectivity with a simple prompt."""
        ai_cfg = self.config.get("ai", {})
        provider = ai_cfg.get("provider", "gemini")
        print(f"{Fore.CYAN}Initializing {provider} client and sending test prompt...")
        try:
            response = self.llm.generate(prompt)
            if response:
                print(f"{Fore.GREEN}\nAI Response ({provider}):")
                print(f"{Fore.WHITE}{response.strip()}")
            else:
                print(f"{Fore.RED}\nAI returned empty response. Check API key/Ollama.")
        except Exception as error:
            print(f"{Fore.RED}\nAI Check failed: {error}")
            sys.exit(1)

    def find_network(self, job_id: str) -> None:
        """Search for professional contacts at the job's company."""
        extractor = JobDetailsExtractor(None)
        job = extractor.get_cached_job(job_id)
        if not job:
            print(f"{Fore.RED}Job {job_id} not found.")
            return

        matches = self.referral_service.find_potential_connections(job)
        print(f"{Fore.CYAN}\nFound {len(matches)} connections at {job.company}:")
        for conn in matches:
            print(f"- {Fore.WHITE}{conn.full_name} {Fore.YELLOW}({conn.position})")

    def map_all_networks(self) -> None:
        """Map professional connections to all cached jobs."""
        print(f"{Fore.CYAN}Mapping connections across all available jobs...")

        extractor = JobDetailsExtractor(None)
        if not extractor.db:
            print(f"{Fore.RED}Database not available.")
            return

        all_jobs_data = extractor.db.get_all_jobs(limit=1000)
        jobs_with_connections = 0
        total_connections = 0

        for job_data in all_jobs_data:
            job = extractor.get_cached_job(job_data["id"])
            if not job:
                continue

            matches = self.referral_service.find_potential_connections(job)
            if matches:
                jobs_with_connections += 1
                total_connections += len(matches)
                print(f"\n{Fore.GREEN}[{job.id}] {Fore.WHITE}{job.title} {Fore.YELLOW}@ {job.company}")
                for conn in matches:
                    print(f"  - {Fore.CYAN}{conn.full_name} {Fore.WHITE}({conn.position})")

        print(f"\n{Fore.CYAN}{'=' * 40}")
        print(f"{Fore.GREEN}Summary: Found {total_connections} connections across {jobs_with_connections} jobs.")
        print(f"{Fore.CYAN}{'=' * 40}")

    def prune(self) -> None:
        """Prune orphaned records from Obsidian."""
        from src.generator.sync_service import SyncService

        SyncService(self.config).prune_vault()

    def _filter_jobs(self, jobs: List[Any]) -> List[Any]:
        """Filters jobs based on exclude_keywords in configuration."""
        exclude = self.config.get("search", {}).get("exclude_keywords", [])
        if not exclude:
            return jobs

        filtered = []
        for job in jobs:
            title = (getattr(job, "title", "") or job.get("title", "") or "").lower()
            if not any(word.lower() in title for word in exclude):
                filtered.append(job)
            else:
                logger.debug(f"Filtering out job due to keyword match: {title}")

        return filtered
