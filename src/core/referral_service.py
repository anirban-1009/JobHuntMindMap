import pathlib
from typing import Any, Dict, List

from src.core.ai import LLMClient
from src.core.network_graph import Connection, NetworkGraphBuilder
from src.ingest.job_details_extractor import JobDetails, JobDetailsExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ReferralService:
    """Manages the generation and storage of referral messages."""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        """
        Initialize the ReferralService.

        Args:
            llm_client: LLM client for message generation.
            config: Application configuration.
        """
        self.llm = llm_client
        self.config = config
        self.db = JobDetailsExtractor(None).db  # Shared DB connection

    def find_potential_connections(self, job: JobDetails) -> List[Connection]:
        """Finds connections at the job's company."""
        user_cfg = self.config.get("user", {})
        conn_path = user_cfg.get("linkedin_connections_path") or self.config.get("network", {}).get("connections_path")
        connections_path = pathlib.Path(conn_path or "data/Connections.csv")

        if not connections_path.exists():
            return []

        builder = NetworkGraphBuilder(connections_path, metadata_path=user_cfg.get("linkedin_metadata_path"))
        return builder.find_matches(job)

    def generate_message(self, job: JobDetails, connection: Any, resume_data: Dict[str, Any]) -> str:
        """Generates a personalized referral request message."""
        # Format skills nicely
        skills_str = "None identified"
        if isinstance(resume_data.get("skills"), dict):
            all_skills = []
            for cat, items in resume_data["skills"].items():
                if isinstance(items, list):
                    all_skills.extend(items)
            skills_str = ", ".join(all_skills[:10])

        connection_name = getattr(connection, "full_name", "Professional")
        first_name = connection_name.split()[0] if " " in connection_name else connection_name
        candidate_first_name = resume_data.get("first_name", "Anirban")

        prompt = f"""
        Generate a short, natural, and polite LinkedIn message to ask for a referral.
        Target Job: {job.title} at {job.company}
        Target Person: {connection_name}
        
        Candidate: {candidate_first_name} {resume_data.get("last_name", "Sikdar")}
        Top Skill: {skills_str.split(",")[0] if skills_str != "None identified" else "technical background"}

        Guidelines:
        - CRITICAL: Total length MUST be under 190 characters.
        - Tone: Warm, human, and professional (not robotic).
        - Flow: "Hi {first_name}, I'm {candidate_first_name}..." or similar natural opening.
        - Content: Briefly mention interest in the {job.title} role and your fit, then ask if they'd be open to referring you.
        - NO subject lines, NO placeholders.
        """
        return self.llm.generate(prompt).strip()

    def save_referral(self, job_id: str, connection_name: str, message: str, profile_url: str = "https://linkedin.com"):
        """Saves the referral request to the database."""
        if self.db:
            self.db.save_request(
                job_id=job_id, connection_name=connection_name, profile_url=profile_url, message=message
            )
            return True
        return False
