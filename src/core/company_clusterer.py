import re
from typing import Any, Dict, List, Tuple

from src.core.company_scorer import CompanyEvaluation
from src.utils.logger import get_logger

logger = get_logger(__name__)


class CompanyClusterer:
    """
    Clusters companies into:
    1. Strategic Action Clusters (Outreach Playbook):
       - Warm Outreach (Referral Priority)
       - Direct Apply & Cold Outreach
       - Network Nurture
       - Watchlist
    2. Domain / Specialization Clusters:
       - Generative AI & LLMs
       - Core ML & Computer Vision
       - Enterprise AI & Cloud Platforms
       - FinTech & E-Commerce AI
       - Healthcare & BioTech AI
       - General Tech & Services
    """

    # Domain keyword patterns
    DOMAIN_PATTERNS = {
        "Generative AI & LLMs": [
            r"\bllm\b",
            r"\bgenai\b",
            r"generative ai",
            r"agentic",
            r"foundation model",
            r"\brag\b",
            r"prompt engineering",
            r"large language",
            r"transformer",
            r"diffusion",
        ],
        "Core ML & Computer Vision": [
            r"computer vision",
            r"\bcv\b",
            r"image",
            r"video",
            r"object detection",
            r"deep learning",
            r"pytorch",
            r"tensorflow",
            r"speech",
            r"audio",
            r"perception",
        ],
        "Enterprise AI & Cloud Platforms": [
            r"cloud",
            r"infrastructure",
            r"\bmlops\b",
            r"developer tools",
            r"data platform",
            r"distributed",
            r"microservices",
            r"kubernetes",
            r"enterprise saas",
            r"pipeline",
        ],
        "FinTech & E-Commerce AI": [
            r"fintech",
            r"financial",
            r"banking",
            r"payments",
            r"fraud",
            r"risk",
            r"trading",
            r"e-commerce",
            r"ecommerce",
            r"retail",
            r"marketplace",
        ],
        "Healthcare & BioTech AI": [
            r"health",
            r"healthcare",
            r"clinical",
            r"medical",
            r"pharma",
            r"biotech",
            r"genomic",
            r"life sciences",
            r"patient",
            r"diagnostic",
        ],
    }

    @classmethod
    def assign_action_cluster(cls, evaluation: CompanyEvaluation) -> Tuple[str, str]:
        """
        Determines the strategic action cluster and specific next-step directive.

        Returns:
            Tuple[str, str]: (cluster_name, recommended_action)
        """
        has_high_match_jobs = evaluation.job_fit_score >= 65 or evaluation.high_match_job_count >= 1
        has_network = evaluation.network_score >= 25 or evaluation.connection_count >= 1

        if has_high_match_jobs and has_network:
            cluster = "Warm Outreach"
            if evaluation.key_contacts:
                top_c = evaluation.key_contacts[0]
                action = (
                    f"Request internal referral from {top_c['name']} ({top_c['title']}) before submitting application."
                )
            else:
                action = "Reach out to internal connections for a referral before applying."
        elif has_high_match_jobs and not has_network:
            cluster = "Direct Apply"
            action = (
                "Submit application directly via career site; find and send cold message "
                "to hiring manager or technical recruiter."
            )
        elif not has_high_match_jobs and has_network:
            cluster = "Network Nurture"
            action = (
                "No urgent high-matching role currently open. Connect for an informational chat "
                "or keep in touch to stay top-of-mind for upcoming openings."
            )
        else:
            cluster = "Watchlist"
            action = "Monitor company career page for new AI/ML openings matching your profile."

        return cluster, action

    @classmethod
    def assign_domain_cluster(cls, company_name: str, jobs: List[Dict[str, Any]]) -> str:
        """
        Determines the primary tech/domain cluster from company name, industries, and job postings.
        """
        corpus = (company_name + " ").lower()
        for j in jobs:
            corpus += " " + (j.get("title") or "").lower()
            corpus += " " + (j.get("specialization") or "").lower()
            corpus += " " + (j.get("industries") or "").lower()
            corpus += " " + (j.get("job_function") or "").lower()
            desc = j.get("description") or ""
            corpus += " " + desc[:300].lower()

        scores = {}
        for domain, patterns in cls.DOMAIN_PATTERNS.items():
            match_count = 0
            for pat in patterns:
                matches = re.findall(pat, corpus, re.IGNORECASE)
                match_count += len(matches)
            scores[domain] = match_count

        best_domain, count = max(scores.items(), key=lambda item: item[1])
        if count >= 2:
            return best_domain

        return "General Tech & Services"

    def process_evaluations(
        self,
        evaluations: List[CompanyEvaluation],
        company_jobs_map: Dict[str, List[Dict[str, Any]]],
    ) -> List[CompanyEvaluation]:
        """
        Updates each CompanyEvaluation with its assigned action cluster, recommended action,
        and domain cluster.
        """
        for ev in evaluations:
            jobs = company_jobs_map.get(ev.name, [])
            action_cluster, recommended_action = self.assign_action_cluster(ev)
            domain_cluster = self.assign_domain_cluster(ev.name, jobs)

            ev.action_cluster = action_cluster
            ev.recommended_action = recommended_action
            ev.domain_cluster = domain_cluster

            # Update breakdown dictionary
            ev.breakdown["action_cluster"] = action_cluster
            ev.breakdown["domain_cluster"] = domain_cluster
            ev.breakdown["recommended_action"] = recommended_action

        return evaluations
