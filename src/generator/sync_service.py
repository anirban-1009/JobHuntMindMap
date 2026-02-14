import json
import pathlib
from typing import Any, Dict

from src.core.relevance_scorer import ScoringResult
from src.generator.dashboard_generator import DashboardGenerator
from src.generator.template_manager import TemplateManager
from src.generator.vault_manager import VaultManager
from src.ingest.job_details_extractor import JobDetails, JobDetailsExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SyncService:
    """Orchestrates the synchronization of data to Obsidian."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vault_manager = VaultManager(config)
        self.template_manager = TemplateManager()
        self.dashboard_generator = DashboardGenerator(config)
        self.extractor = JobDetailsExtractor(None)  # Used for cache access

    def sync(self) -> None:
        """Syncs jobs, companies, and analysis to the Obsidian Vault."""
        logger.info("Starting Obsidian sync...")

        # 1. Ensure Vault Folders Exist
        self.vault_manager.ensure_folders_exist()

        # 2. Sync Jobs and Companies
        self._sync_jobs_and_companies()

        # 3. Generate Dashboard
        self.dashboard_generator.generate()

        logger.info("Obsidian sync complete.")

    def _sync_jobs_and_companies(self) -> None:
        """Reads cached jobs and writes them to the Vault."""
        cache_dir = pathlib.Path("data/job_cache")
        if not cache_dir.exists():
            logger.warning("Job cache directory not found. Nothing to sync.")
            return

        # Track companies to generate company notes later
        companies = set()

        for job_file in cache_dir.glob("*.json"):
            # Skip analysis files, looking only for job files (numeric IDs)
            if "_" in job_file.stem or not job_file.stem.isdigit():
                continue

            job_id = job_file.stem
            job = self.extractor.get_cached_job(job_id)
            if not job:
                continue

            # Load Analysis if available
            score = self._load_analysis(job_id)

            # Generate Job Note
            self._write_job_note(job, score)

            # Track Company
            if job.company and job.company != "Unknown":
                companies.add(job.company)

        # Generate Company Notes
        for company_name in companies:
            self._write_company_note(company_name)

    def _load_analysis(self, job_id: str) -> ScoringResult:
        """Loads analysis for a job, returning a default if not found."""
        analysis_path = pathlib.Path(f"data/job_cache/{job_id}_analysis.json")
        if analysis_path.exists():
            try:
                with open(analysis_path, "r") as f:
                    data = json.load(f)
                    return ScoringResult(**data)
            except Exception as e:
                logger.warning(f"Failed to load analysis for {job_id}: {e}")

        # Default "Unscored" Result
        return ScoringResult(
            score=0,
            reasoning="Job has not been scored yet. Run 'score' command.",
            matching_skills=[],
            missing_skills=[],
        )

    def _write_job_note(self, job: JobDetails, score: ScoringResult) -> None:
        """Render and write a Job note."""
        try:
            # Determine grouping based on job role/specialization
            specialization = self._determine_specialization(job)

            content = self.template_manager.render_job(job, score, specialization=specialization)
            filename = f"{job.title} - {job.company}.md"

            self.vault_manager.write_file(content, filename, "jobs", subfolder=specialization)
        except Exception as e:
            logger.error(f"Failed to write job note for {job.id}: {e}")

    def _determine_specialization(self, job: JobDetails) -> str:
        """Categorize job into typical tech specializations."""
        title = job.title.lower()

        if any(
            x in title
            for x in [
                "machine learning",
                "ml",
                "ai ",
                "artificial intelligence",
                "nlp",
                "computer vision",
                "generative ai",
                "llm",
                "deep learning",
                "transformers",
                "pytorch",
                "tensorflow",
                "neural",
            ]
        ):
            return "AI_ML"
        if any(x in title for x in ["data scientist", "data analyst", "data engineer", "big data", "analytics"]):
            return "Data_Science"
        if any(x in title for x in ["python", "django", "flask", "fastapi", "numpy", "pandas"]):
            return "Python_Dev"
        if any(
            x in title
            for x in ["backend", "back-end", "server", "distributed systems", "api engineer", "platform engineer"]
        ):
            return "Backend"
        if any(
            x in title
            for x in [
                "frontend",
                "front-end",
                "react",
                "vue",
                "angular",
                "javascript",
                "typescript",
                "ui/ux",
                "web developer",
            ]
        ):
            return "Frontend"
        if any(
            x in title
            for x in ["devops", "sre", "cloud", "aws", "azure", "gcp", "infrastructure", "kubernetes", "docker"]
        ):
            return "DevOps_Cloud"
        if any(x in title for x in ["full stack", "fullstack"]):
            return "FullStack"

        return "General"

    def _write_company_note(self, company_name: str) -> None:
        """Render and write a Company note."""
        # Check if it already exists to avoid overwriting user notes
        if self.vault_manager.file_exists(f"{company_name}.md", "companies"):
            return

        try:
            # For now, we generate a basic placeholder.
            # Future enhancements could scrape company details or aggregate job stats.
            content = self.template_manager.render_company(
                name=company_name,
                industry="Unknown",
                location="Unknown",
                jobs=[],  # We could link back to jobs here in the future
            )
            filename = f"{company_name}.md"
            self.vault_manager.write_file(content, filename, "companies")
        except Exception as e:
            logger.error(f"Failed to write company note for {company_name}: {e}")
