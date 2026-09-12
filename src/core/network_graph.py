import json
import pathlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.ingest.job_details_extractor import JobDetails
from src.ingest.linkedin_parser import LinkedInParser
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ConnectionMetadata:
    """Extra tracking data for a LinkedIn connection."""

    last_contacted: Optional[str] = None
    achievements: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class Connection:
    """Represents a LinkedIn connection with metadata."""

    first_name: str
    last_name: str
    company: Optional[str]
    position: Optional[str]
    connected_on: str
    metadata: ConnectionMetadata = field(default_factory=ConnectionMetadata)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class NetworkGraphBuilder:
    """Matches job opportunities with professional connections."""

    def __init__(self, connections_path: pathlib.Path, metadata_path: Optional[pathlib.Path] = None):
        """
        Initialize the NetworkGraphBuilder.

        Args:
            connections_path: Path to the Connections.csv file.
            metadata_path: Path to the JSON file for connection metadata.
        """
        self.parser = LinkedInParser(connections_path)
        self.metadata_path = metadata_path or pathlib.Path("data/network_metadata.json")
        self.connections: List[Connection] = []
        self._load_data()

    def _load_data(self):
        """Loads connections and merges with metadata."""
        try:
            raw_connections = self.parser.parse_connections()
            metadata = self._load_metadata()

            self.connections = []
            for raw in raw_connections:
                conn_id = f"{raw['first_name']}_{raw['last_name']}_{raw['connected_on']}"
                meta_dict = metadata.get(conn_id, {})

                meta = ConnectionMetadata(
                    last_contacted=meta_dict.get("last_contacted"),
                    achievements=meta_dict.get("achievements", []),
                    notes=meta_dict.get("notes"),
                )

                self.connections.append(
                    Connection(
                        first_name=raw["first_name"],
                        last_name=raw["last_name"],
                        company=raw["company"],
                        position=raw["position"],
                        connected_on=raw["connected_on"],
                        metadata=meta,
                    )
                )
        except Exception as e:
            logger.error(f"Failed to load network data: {e}")

    def _load_metadata(self) -> Dict[str, Any]:
        """Loads metadata from JSON file."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load metadata file: {e}")
        return {}

    def save_metadata(self):
        """Saves current metadata to JSON file."""
        metadata = {}
        for conn in self.connections:
            # We don't save empty metadata to keep the file clean
            if conn.metadata.last_contacted or conn.metadata.achievements or conn.metadata.notes:
                conn_id = f"{conn.first_name}_{conn.last_name}_{conn.connected_on}"
                metadata[conn_id] = asdict(conn.metadata)

        try:
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def find_matches(self, job: JobDetails) -> List[Connection]:
        """
        Finds connections working at the job's company using sanitized matching.

        Args:
            job: The JobDetails object.

        Returns:
            List[Connection]: List of matching connections.
        """
        if not job.company:
            return []
        return self.find_matches_for_company(job.company)

    def find_matches_for_company(self, company_name: str) -> List[Connection]:
        """
        Finds connections working at a specific company using robust token matching.

        Args:
            company_name: Target company name.

        Returns:
            List[Connection]: List of matching connections.
        """
        if not company_name:
            return []

        target_norm = self._normalize_for_matching(company_name)
        if not target_norm:
            return []

        matches = []
        for conn in self.connections:
            if not conn.company:
                continue
            conn_norm = self._normalize_for_matching(conn.company)
            if self._is_company_match(target_norm, conn_norm):
                matches.append(conn)

        return matches

    def _normalize_for_matching(self, name: str) -> str:
        """Strips legal entity suffixes and punctuation for clean matching."""
        if not name:
            return ""
        s = name.strip()
        s = re.sub(r"(?i)\b(inc|llc|pvt|ltd|technologies|solutions|services|corporation|corp|group)\b\.?", "", s)
        s = re.sub(r"[^a-zA-Z0-9\s]", " ", s)
        return " ".join(s.lower().split())

    def _is_company_match(self, clean1: str, clean2: str) -> bool:
        """Determines if two normalized company names represent the same company."""
        if not clean1 or not clean2:
            return False
        if clean1 == clean2:
            return True

        # Punctuation/spacing collapsed match (e.g. Build-It vs BuildIt)
        s1 = self._sanitize_for_search(clean1)
        s2 = self._sanitize_for_search(clean2)
        if s1 and s2 and s1 == s2:
            return True

        words1 = clean1.split()
        words2 = clean2.split()
        set1, set2 = set(words1), set(words2)

        # Subset match on significant words (> 2 chars)
        sig1 = {w for w in set1 if len(w) > 2}
        sig2 = {w for w in set2 if len(w) > 2}
        if sig1 and sig2 and (sig1.issubset(sig2) or sig2.issubset(sig1)):
            return True

        # Word boundary substring match if long enough
        if len(clean1) >= 4 and re.search(r"\b" + re.escape(clean1) + r"\b", clean2):
            return True
        if len(clean2) >= 4 and re.search(r"\b" + re.escape(clean2) + r"\b", clean1):
            return True

        return False

    @staticmethod
    def classify_role(position: Optional[str]) -> str:
        """
        Classifies a connection's position into strategic outreach categories:
        - 'talent': Recruiters, sourcers, HR talent partners (highest conversion for fast referral/screening)
        - 'engineering_lead': Engineering managers, leads, directors, CTOs (hiring decision makers)
        - 'peer_engineer': AI/ML engineers, data scientists, software engineers (peer referral candidates)
        - 'other': Other business functions
        """
        if not position:
            return "other"
        pos = position.lower()

        talent_keywords = [
            "recruiter",
            "talent",
            "sourcer",
            "people partner",
            "staffing",
            "human resources",
            "talent acquisition",
        ]
        if any(kw in pos for kw in talent_keywords):
            return "talent"

        lead_keywords = [
            "engineering manager",
            "tech lead",
            "lead engineer",
            "director",
            "head of",
            "principal",
            "founder",
            "co-founder",
            "vp",
            "chief",
            "cto",
            "architect",
        ]
        if any(kw in pos for kw in lead_keywords):
            return "engineering_lead"

        peer_keywords = [
            "ai",
            "machine learning",
            "ml",
            "deep learning",
            "nlp",
            "computer vision",
            "software engineer",
            "sde",
            "data scientist",
            "data engineer",
            "researcher",
            "developer",
        ]
        if any(kw in pos for kw in peer_keywords):
            return "peer_engineer"

        return "other"

    def _sanitize_for_search(self, text: str) -> str:
        """Legacy helper maintained for backward compatibility."""
        if not text:
            return ""
        sanitized = re.sub(r"[^a-zA-Z0-9]", "", text)
        return sanitized.lower()

    def update_connection(self, first_name: str, last_name: str, connected_on: str, **kwargs):
        """
        Updates metadata for a specific connection.

        Args:
            first_name: Connection's first name.
            last_name: Connection's last name.
            connected_on: When they were connected (used for ID uniqueness).
            **kwargs: Metadata fields to update (last_contacted, achievements, notes).
        """
        for conn in self.connections:
            if conn.first_name == first_name and conn.last_name == last_name and conn.connected_on == connected_on:
                if "last_contacted" in kwargs:
                    conn.metadata.last_contacted = kwargs["last_contacted"]
                if "achievements" in kwargs:
                    conn.metadata.achievements = kwargs["achievements"]
                if "notes" in kwargs:
                    conn.metadata.notes = kwargs["notes"]
                break
