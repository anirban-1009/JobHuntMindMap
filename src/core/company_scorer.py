import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.network_graph import Connection, NetworkGraphBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompanyEvaluation:
    """Represents the complete scoring and evaluation result for a company."""

    id: str
    name: str
    score: int
    job_fit_score: int
    company_fit_score: int
    network_score: int
    job_count: int
    high_match_job_count: int
    max_job_score: int
    avg_job_score: float
    connection_count: int
    key_connection_count: int
    target_tier: str
    action_cluster: str = "Watchlist"
    domain_cluster: str = "General Tech & Services"
    recommended_action: str = ""
    breakdown: Dict[str, Any] = field(default_factory=dict)
    key_contacts: List[Dict[str, str]] = field(default_factory=list)
    top_jobs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Converts evaluation to a dictionary suitable for DB storage or JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "job_fit_score": self.job_fit_score,
            "company_fit_score": self.company_fit_score,
            "network_score": self.network_score,
            "job_count": self.job_count,
            "high_match_job_count": self.high_match_job_count,
            "max_job_score": self.max_job_score,
            "avg_job_score": round(self.avg_job_score, 1),
            "connection_count": self.connection_count,
            "key_connection_count": self.key_connection_count,
            "target_tier": self.target_tier,
            "action_cluster": self.action_cluster,
            "domain_cluster": self.domain_cluster,
            "recommended_action": self.recommended_action,
            "evaluation_data": self.breakdown,
        }


class CompanyScorer:
    """
    Evaluates and scores companies based on:
    1. Job Opportunity Quality & Role Match (45%):
       Highest relevance score, density of high-matching roles (>=70), active job volume.
    2. Company Profile & Strategic Domain Fit ("Company About") (35%):
       Alignment of company mission, domain, and products with AI/ML/LLMs vs. generic IT,
       plus priority boost for configured target companies.
    3. Network Leverage (20%):
       Presence of high-leverage referral contacts (Recruiters/Talent, Engineering Managers, Peer Engineers).
    """

    # High-value domain keywords reflecting candidate's core focus (AI/ML Engineer)
    AI_CORE_KEYWORDS = [
        "llm",
        "large language model",
        "generative ai",
        "genai",
        "deep learning",
        "neural network",
        "transformer",
        "agentic",
        "ai engineer",
        "machine learning",
        "nlp",
        "natural language",
        "computer vision",
        "diffusion",
        "reinforcement learning",
        "rag",
        "vector database",
        "fine-tuning",
        "applied ai",
    ]

    AI_PLATFORM_KEYWORDS = [
        "ai platform",
        "foundation models",
        "ai research",
        "mlops",
        "inference",
        "data platform",
        "developer tools",
        "cloud platform",
        "autonomous",
        "intelligent",
    ]

    LEGACY_SERVICE_KEYWORDS = ["staffing", "outsourcing", "recruiting agency", "body shopping", "staff augmentation"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the CompanyScorer with application configuration.
        """
        self.config = config or {}
        self.target_companies = self._extract_target_companies()

    def _extract_target_companies(self) -> Dict[str, str]:
        """Extracts configured target companies and external career sites."""
        targets = {}
        search_cfg = self.config.get("search", {})

        # 1. External sites in config
        for site in search_cfg.get("external_sites", []):
            comp = site.get("company") if isinstance(site, dict) else None
            if comp and comp != "Unknown":
                targets[self._slugify(comp)] = comp

        # 2. Explicit target_companies list if configured
        for comp in search_cfg.get("target_companies", []):
            if comp:
                targets[self._slugify(comp)] = comp

        return targets

    @staticmethod
    def _slugify(name: str) -> str:
        """Generates a clean slug ID for a company name."""
        if not name:
            return ""
        s = re.sub(r"[^a-zA-Z0-9]", "_", name.strip().lower())
        return re.sub(r"_+", "_", s).strip("_")

    def score_company(
        self,
        company_name: str,
        jobs: List[Dict[str, Any]],
        connections: List[Connection],
    ) -> CompanyEvaluation:
        """
        Scores a single company given its open jobs and verified network connections.
        """
        slug_id = self._slugify(company_name)
        job_count = len(jobs)

        # -------------------------------------------------------------
        # 1. Job Opportunity Quality & Role Match (45%)
        # -------------------------------------------------------------
        scores = [
            j.get("relevance_score")
            for j in jobs
            if j.get("relevance_score") is not None and j.get("status") != "rejected"
        ]
        max_job_score = max(scores) if scores else 0
        avg_job_score = sum(scores) / len(scores) if scores else 0.0
        high_match_count = sum(1 for s in scores if s >= 70)

        job_fit_score = 0
        if max_job_score > 0:
            # Base score is the maximum job score
            # Multiple high-match openings add density bonus (up to +15 pts)
            density_bonus = min(15, (high_match_count - 1) * 5) if high_match_count > 1 else 0
            job_fit_score = min(100, max_job_score + density_bonus)

        # -------------------------------------------------------------
        # 2. Company Profile & Strategic Domain Fit ("Company About") (35%)
        # -------------------------------------------------------------
        is_target_company = slug_id in self.target_companies
        target_tier = "Target" if is_target_company else "Standard"

        company_fit_score = self._calculate_company_fit(
            company_name=company_name,
            jobs=jobs,
            is_target_company=is_target_company,
        )

        # -------------------------------------------------------------
        # 3. Network Leverage (20%)
        # -------------------------------------------------------------
        network_score, key_contacts, role_counts = self._calculate_network_leverage(connections)
        key_connection_count = len(key_contacts)
        connection_count = len(connections)

        # -------------------------------------------------------------
        # Composite Weighted Score
        # -------------------------------------------------------------
        composite = round(0.45 * job_fit_score + 0.35 * company_fit_score + 0.20 * network_score)
        composite = max(0, min(100, composite))

        # Sort jobs by relevance score descending
        sorted_jobs = sorted(
            jobs,
            key=lambda x: (x.get("relevance_score") is not None, x.get("relevance_score") or 0),
            reverse=True,
        )
        top_jobs_summary = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "score": j.get("relevance_score"),
                "link": j.get("link") or j.get("apply_link"),
                "status": j.get("status"),
                "specialization": j.get("specialization"),
            }
            for j in sorted_jobs[:5]
        ]

        breakdown = {
            "job_fit_score": job_fit_score,
            "company_fit_score": company_fit_score,
            "network_score": network_score,
            "weights": {"job_fit": 0.45, "company_fit": 0.35, "network": 0.20},
            "is_target_company": is_target_company,
            "role_counts": role_counts,
            "high_match_count": high_match_count,
        }

        return CompanyEvaluation(
            id=slug_id,
            name=company_name,
            score=composite,
            job_fit_score=job_fit_score,
            company_fit_score=company_fit_score,
            network_score=network_score,
            job_count=job_count,
            high_match_job_count=high_match_count,
            max_job_score=max_job_score,
            avg_job_score=avg_job_score,
            connection_count=connection_count,
            key_connection_count=key_connection_count,
            target_tier=target_tier,
            breakdown=breakdown,
            key_contacts=key_contacts,
            top_jobs=top_jobs_summary,
        )

    def _calculate_company_fit(
        self,
        company_name: str,
        jobs: List[Dict[str, Any]],
        is_target_company: bool,
    ) -> int:
        """
        Evaluates how closely the company and its offerings match what the user is looking for.
        """
        # Explicit target companies configured by user start with a high baseline
        if is_target_company:
            base_score = 92
        else:
            base_score = 50

        # Combine titles, descriptions, and industries for domain text analysis
        combined_text = (company_name + " ").lower()
        for j in jobs:
            combined_text += " " + (j.get("title") or "").lower()
            combined_text += " " + (j.get("industries") or "").lower()
            combined_text += " " + (j.get("job_function") or "").lower()
            # Sample first 400 chars of description to capture company "about" and team intro
            desc = j.get("description") or ""
            combined_text += " " + desc[:400].lower()

        # Check for core AI/ML keyword matches
        core_hits = sum(1 for kw in self.AI_CORE_KEYWORDS if kw in combined_text)
        platform_hits = sum(1 for kw in self.AI_PLATFORM_KEYWORDS if kw in combined_text)
        legacy_hits = sum(1 for kw in self.LEGACY_SERVICE_KEYWORDS if kw in combined_text)

        # Points for domain alignment
        domain_points = min(40, core_hits * 8 + platform_hits * 4)
        penalty = min(25, legacy_hits * 12)

        fit_score = base_score + domain_points - penalty
        return max(20, min(100, fit_score))

    def _calculate_network_leverage(
        self,
        connections: List[Connection],
    ) -> tuple[int, List[Dict[str, str]], Dict[str, int]]:
        """
        Evaluates network leverage:
        Identifies key contacts (Recruiters, Engineering Managers, Peer Engineers)
        and computes network leverage score (0-100).
        """
        if not connections:
            return 0, [], {"talent": 0, "engineering_lead": 0, "peer_engineer": 0, "other": 0}

        key_contacts = []
        role_counts = {"talent": 0, "engineering_lead": 0, "peer_engineer": 0, "other": 0}

        for conn in connections:
            role_type = NetworkGraphBuilder.classify_role(conn.position)
            role_counts[role_type] = role_counts.get(role_type, 0) + 1

            if role_type in ("talent", "engineering_lead", "peer_engineer"):
                key_contacts.append(
                    {
                        "name": conn.full_name,
                        "title": conn.position or "Professional",
                        "role_type": role_type,
                        "connected_on": conn.connected_on,
                        "last_contacted": conn.metadata.last_contacted if hasattr(conn, "metadata") else None,
                    }
                )

        # Priority order for key contacts: talent first (fastest referral), then engineering leadership, then peers
        role_priority = {"talent": 1, "engineering_lead": 2, "peer_engineer": 3, "other": 4}
        key_contacts.sort(key=lambda c: role_priority.get(c["role_type"], 5))

        # Calculate network score based on contact leverage
        talent_pts = 40 if role_counts["talent"] >= 1 else 0
        lead_pts = 35 if role_counts["engineering_lead"] >= 1 else 0
        peer_pts = min(30, role_counts["peer_engineer"] * 15)
        other_pts = min(15, role_counts["other"] * 5)

        network_score = min(100, talent_pts + lead_pts + peer_pts + other_pts)
        # Even with only 'other' connections, having connections is worth at least 25
        if connections and network_score < 25:
            network_score = 25

        return network_score, key_contacts, role_counts
