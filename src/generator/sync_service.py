import json
import re
from typing import Any, Dict, Set

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
        """Reads jobs from the database and writes them to the Vault."""
        if not self.extractor.db:
            logger.warning("Database not available. Nothing to sync.")
            return

        all_jobs_data = self.extractor.db.get_all_jobs(limit=10000)
        if not all_jobs_data:
            logger.warning("No jobs found in database to sync.")
            return

        logger.info(f"Syncing {len(all_jobs_data)} jobs from database...")

        # Track companies to generate company notes later
        companies = set()
        synced_count = 0

        for job_data in all_jobs_data:
            job_id = job_data["id"]
            job = self.extractor.get_cached_job(job_id)
            if not job:
                logger.warning(f"Could not load job {job_id} for sync.")
                continue

            # Load Analysis if available (from DB)
            score = self._load_analysis(job_data)

            # Generate Job Note
            self._write_job_note(job, score)
            synced_count += 1

            # Track Company
            if job.company and job.company != "Unknown":
                companies.add(job.company)

        logger.info(f"Synced {synced_count} job notes.")

        # Generate Company Notes
        for company_name in companies:
            self._write_company_note(company_name)

        logger.info(f"Synced {len(companies)} company notes.")

    def _load_analysis(self, job_data: Dict[str, Any]) -> ScoringResult:
        """Loads analysis for a job from DB record, returning a default if not found."""
        analysis_json = job_data.get("analysis_data")
        if analysis_json:
            try:
                data = json.loads(analysis_json)
                return ScoringResult(**data)
            except Exception as e:
                logger.warning(f"Failed to load analysis for job {job_data.get('id')}: {e}")

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

    def prune_vault(self) -> None:
        """Removes job files from the vault that are no longer in the database."""
        logger.info("Pruning Obsidian vault...")

        if not self.extractor.db:
            logger.error("Database not available for pruning.")
            return

        db_jobs = self.extractor.db.get_all_jobs(limit=10000)
        db_ids: Set[str] = {str(job["id"]) for job in db_jobs}

        jobs_folder = self.vault_manager.vault_path / self.vault_manager.folders.get("jobs", "Jobs")
        if not jobs_folder.exists():
            logger.warning(f"Jobs folder not found at {jobs_folder}")
            return

        removed_count = 0
        for file_path in jobs_folder.rglob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                # Look for "- **Job ID:** {id}"
                match = re.search(r"- \*\*Job ID:\*\* (\d+)", content)
                if match:
                    job_id = match.group(1)
                    if job_id not in db_ids:
                        logger.info(f"Removing orphaned job note: {file_path.name} (ID: {job_id})")
                        file_path.unlink()
                        removed_count += 1
            except Exception as e:
                logger.warning(f"Could not process {file_path}: {e}")

        logger.info(f"Pruning complete. Removed {removed_count} orphaned job notes.")
