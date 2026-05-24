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

    def generate_message(
        self, job: JobDetails, connection: Any, resume_data: Dict[str, Any], max_chars: int = 250
    ) -> str:
        """
        Generates a personalized referral request message.

        The message is limited to the specified max_chars to fit within
        the target platform's (e.g. LinkedIn) constraints.
        Enriches the message with experience details and ensures diversity.
        """
        # 1. Format skills nicely
        skills_str = "None identified"
        if isinstance(resume_data.get("skills"), dict):
            all_skills = []
            for cat, items in resume_data["skills"].items():
                if isinstance(items, list):
                    all_skills.extend(items)
            skills_str = ", ".join(all_skills[:8])

        # 2. Extract Experience info
        experience_list = resume_data.get("experience", [])
        total_exp_years = self.config.get("user", {}).get("total_experience_years") or resume_data.get(
            "total_experience_years", len(experience_list) * 2
        )
        current_role = resume_data.get("job_title", "Software Engineer")

        if experience_list and not resume_data.get("job_title"):
            current_role = experience_list[0].get("title", current_role)

        connection_name = getattr(connection, "full_name", "Professional")
        first_name = connection_name.split()[0] if " " in connection_name else connection_name
        candidate_first_name = resume_data.get("first_name", "Anirban")
        candidate_full_name = f"{candidate_first_name} {resume_data.get('last_name', 'Sikdar')}"

        prompt = f"""
        Generate a highly personalized, natural, and polite LinkedIn message to ask for a job referral.
        
        CONTEXT:
        - Target: {job.title} at {job.company}
        - To: {connection_name}
        - From: {candidate_full_name}
        - Current Role: {current_role}
        - Total Experience: ~{total_exp_years}+ years
        - Key Skills: {skills_str}

        CRITICAL GUIDELINES:
        1. LENGTH: Must be under {max_chars} characters.
        2. NO ROBOTIC TEMPLATES: Avoid "I am writing to express interest". Use natural spoken English.
        3. DIVERSITY: Be creative. You can start with a shared company (if they are at the target company), a compliment on their work/profile, or a direct but warm approach.
        4. EXPERIENCE: Briefly mention {total_exp_years}+ years of experience or the current role {current_role} if it adds value.
        5. CALL TO ACTION: Ask if they'd be open to sharing my profile/referring me, or if they have advice for the {job.title} role.
        6. NO placeholders [like this], NO subject lines.

        Example Styles (Pick one or mix):
        - Style A: Hi {first_name}, I'm {candidate_first_name}. I've been following {job.company}'s work in tech...
        - Style B: Hey {first_name}, hope you're doing well! I'm a {current_role} with {total_exp_years}y exp, interested in the {job.title} opening...
        - Style C: Hi {first_name}, I saw you're at {job.company}. I'm applying for the {job.title} role and was wondering if you'd be open to a quick chat or referral?
        """
        message = self.llm.generate(prompt).strip()

        # Clean up any quotes the LLM might include
        message = message.strip('"').strip("'")

        if len(message) > max_chars:
            logger.warning(
                f"Generated message exceeds {max_chars} chars ({len(message)}). Keeping full message as requested."
            )

        return message

    def save_referral(self, job_id: str, connection_name: str, message: str, profile_url: str = "https://linkedin.com"):
        """Saves the referral request to the database."""
        if self.db:
            self.db.save_request(
                job_id=job_id, connection_name=connection_name, profile_url=profile_url, message=message
            )
            return True
        return False
