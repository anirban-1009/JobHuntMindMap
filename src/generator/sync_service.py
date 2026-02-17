import json
import pathlib
import re
from typing import Any, Dict, List, Set

from src.core.network_graph import NetworkGraphBuilder
from src.core.referral_service import ReferralService
from src.core.relevance_scorer import ScoringResult
from src.generator.dashboard_generator import DashboardGenerator
from src.generator.template_manager import TemplateManager
from src.generator.vault_manager import VaultManager
from src.ingest.job_details_extractor import JobDetailsExtractor
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
        self.referral_service = ReferralService(None, config)  # LLM not needed for matching

    def sync(self) -> None:
        """Syncs jobs, companies, and analysis to the Obsidian Vault."""
        logger.info("Starting Obsidian sync...")

        # 1. Ensure Vault Folders Exist
        self.vault_manager.ensure_folders_exist()

        # 2. Sync Jobs and Companies
        self._sync_all()

        # 3. Generate Dashboard
        self.dashboard_generator.generate()

        logger.info("Obsidian sync complete.")

    def _sync_all(self) -> None:
        """Reads jobs and connections and writes them to the Vault with links."""
        if not self.extractor.db:
            logger.warning("Database not available. Nothing to sync.")
            return

        all_jobs_data = self.extractor.db.get_all_jobs(limit=10000)
        jobs: List[Dict[str, Any]] = []
        for jd in all_jobs_data:
            job_obj = self.extractor.get_cached_job(jd["id"])
            if job_obj:
                score = self._load_analysis(jd)
                jobs.append({"details": job_obj, "score": score})

        # Prepare paths for NetworkGraphBuilder
        user_cfg = self.config.get("user", {})
        conn_path = user_cfg.get("linkedin_connections_path") or self.config.get("network", {}).get("connections_path")
        connections_path = pathlib.Path(conn_path or "data/Connections.csv")

        builder = NetworkGraphBuilder(connections_path, metadata_path=user_cfg.get("linkedin_metadata_path"))
        all_connections = builder.connections

        # Prepare Lookups
        company_to_jobs = {}
        company_to_people = {}

        for j in jobs:
            co = j["details"].company
            if co:
                if co not in company_to_jobs:
                    company_to_jobs[co] = []
                company_to_jobs[co].append(j)

        for p in all_connections:
            co = p.company
            if co:
                if co not in company_to_people:
                    company_to_people[co] = []
                company_to_people[co].append(p)

        # 1. Sync People
        for person in all_connections:
            # Jobs at their company
            p_company = person.company
            associated_jobs = []
            if p_company in company_to_jobs:
                for j in company_to_jobs[p_company]:
                    associated_jobs.append(
                        {
                            "title": j["details"].title,
                            "filename": f"{j['details'].title} - {j['details'].company}",
                            "status": "To Apply",  # Optional: get from DB
                        }
                    )

            if not associated_jobs:
                continue

            content = self.template_manager.render_person(person, jobs=associated_jobs)
            self.vault_manager.write_file(content, f"{person.full_name}.md", "people")

        # 2. Sync Jobs
        for j in jobs:
            job = j["details"]
            score = j["score"]

            # People at this company
            people_at_co = []
            if job.company in company_to_people:
                for p in company_to_people[job.company]:
                    people_at_co.append({"name": p.full_name, "filename": f"{p.full_name}", "title": p.position})

            # specialization = self._determine_specialization(job)
            specialization = job.specialization
            content = self.template_manager.render_job(job, score, specialization=specialization, people=people_at_co)
            filename = f"{job.title} - {job.company}.md"
            self.vault_manager.write_file(content, filename, "jobs", subfolder=specialization)

        # 3. Sync Companies
        all_companies = set(list(company_to_jobs.keys()) + list(company_to_people.keys()))
        for co in all_companies:
            co_jobs = []
            if co in company_to_jobs:
                for j in company_to_jobs[co]:
                    co_jobs.append(
                        {
                            "title": j["details"].title,
                            "filename": f"{j['details'].title} - {j['details'].company}",
                            "status": "Active",
                        }
                    )

            if not co_jobs:
                continue

            co_people = []
            if co in company_to_people:
                for p in company_to_people[co]:
                    co_people.append({"name": p.full_name, "filename": f"{p.full_name}", "title": p.position})

            content = self.template_manager.render_company(name=co, jobs=co_jobs, people=co_people)
            self.vault_manager.write_file(content, f"{co}.md", "companies")

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

        # 2. Prune People and Companies (ones with no jobs)
        for folder_key in ["people", "companies"]:
            folder = self.vault_manager.vault_path / self.vault_manager.folders.get(folder_key)
            if not folder.exists():
                continue

            for file_path in folder.glob("*.md"):
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if "No jobs found at this company." in content or "jobs: []" in content:
                        logger.info(f"Removing unlinked note from {folder_key}: {file_path.name}")
                        file_path.unlink()
                        removed_count += 1
                except Exception as e:
                    logger.warning(f"Error pruning {file_path}: {e}")

        logger.info(f"Pruning complete. Removed {removed_count} Orphaned notes.")

    def sync_from_obsidian(self) -> None:
        """Parses Obsidian job notes to update status and other metadata in the database."""
        logger.info("Syncing back from Obsidian to database...")

        if not self.extractor.db:
            logger.error("Database not available for sync-back.")
            return

        jobs_folder = self.vault_manager.vault_path / self.vault_manager.folders.get("jobs", "Jobs")
        if not jobs_folder.exists():
            logger.warning(f"Jobs folder not found at {jobs_folder}")
            return

        # Status Tag Mapping
        tag_map = {
            "#ToApply": "to_apply",
            "#Applied": "applied",
            "#Interviewing": "interviewing",
            "#Rejected": "rejected",
            "#Offered": "offered",
            "#Wishlist": "wishlist",
        }

        updated_count = 0
        for file_path in jobs_folder.rglob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                # 1. Extract Job ID
                id_match = re.search(r"- \*\*Job ID:\*\* (\d+)", content)
                if not id_match:
                    continue
                job_id = id_match.group(1)

                # 2. Extract Status Tag
                # Look for tags in the "Status:" line or anywhere in the file
                # But typically we put them in the status line: - **Status:** #ToApply #Specialization
                status_line_match = re.search(r"- \*\*Status:\*\* (.*)", content)
                if status_line_match:
                    line_content = status_line_match.group(1)
                    found_status = None
                    for tag, status_val in tag_map.items():
                        if tag in line_content:
                            found_status = status_val
                            break

                    if found_status:
                        if self.extractor.db.job_exists(job_id):
                            self.extractor.db.update_job_status(job_id, found_status)
                            updated_count += 1
                        else:
                            logger.warning(
                                f"Job ID {job_id} found in Obsidian ({file_path.name}) but not in database. Skipping."
                            )

            except Exception as e:
                logger.warning(f"Error processing {file_path} for sync-back: {e}")

        logger.info(f"Sync-back complete. Updated {updated_count} jobs.")
