from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core.ai import LLMClient
from src.core.relevance_scorer import ScoringResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GapAnalysisResult:
    """Result of the gap analysis."""

    top_missing_skills: List[str]
    skill_frequency: Dict[str, int]
    improvement_plan: str


class GapAnalyzer:
    """Analyzes missing skills across multiple job applications to identify learning opportunities."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def analyze_gaps(self, scoring_results: List[ScoringResult], top_n: int = 5) -> Optional[GapAnalysisResult]:
        """
        Aggregates missing skills from a list of scoring results and generates an improvement plan.

        Args:
            scoring_results: List of ScoringResult objects from RelevanceScorer.
            top_n: Number of top missing skills to focus on.

        Returns:
            GapAnalysisResult containing aggregated data and advice, or None if analysis fails.
        """
        if not scoring_results:
            logger.warning("No scoring results provided for gap analysis.")
            return None

        # 1. Aggregate missing skills
        all_missing_skills = []
        for res in scoring_results:
            # We can optionally weight this by job score, but frequency is a good start.
            # Normalization (lowercase, strip) is done here to avoid "Python" vs "python".
            normalized_skills = [s.strip().lower() for s in res.missing_skills]
            all_missing_skills.extend(normalized_skills)

        if not all_missing_skills:
            logger.info("No missing skills found in the provided results.")
            return GapAnalysisResult(
                top_missing_skills=[],
                skill_frequency={},
                improvement_plan="No major gaps identified! You are a strong candidate.",
            )

        # 2. Calculate Frequency
        counter = Counter(all_missing_skills)
        most_common = counter.most_common(top_n)
        top_skills = [skill for skill, count in most_common]
        frequency_dict = dict(most_common)

        # 3. Generate Improvement Plan via LLM
        plan = self._generate_improvement_plan(top_skills)

        return GapAnalysisResult(top_missing_skills=top_skills, skill_frequency=frequency_dict, improvement_plan=plan)

    def _generate_improvement_plan(self, missing_skills: List[str]) -> str:
        """Uses LLM to suggest how to close the identified skill gaps."""
        skills_str = ", ".join(missing_skills)
        prompt = f"""
        I have analyzed multiple job descriptions and identified the following recurring missing skills in my profile:
        {skills_str}

        Act as a senior career coach.
        1. Briefly explain why these skills are important in the current market.
        2. Propose a concrete, actionable learning path to acquire these skills efficiently.
        3. Suggest a project idea that would demonstrate proficiency in these areas combined.

        Keep the response concise, encouraging, and actionable.
        """

        system_instruction = "You are a pragmatic technical career coach focused on efficient upskilling."

        try:
            plan = self.llm.generate(prompt, system_instruction)
            return plan or "Could not generate improvement plan."
        except Exception as e:
            logger.error(f"Error generating improvement plan: {e}")
            return "Error generating improvement plan."
