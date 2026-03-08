import re
from dataclasses import dataclass
from typing import List, Optional

from src.core.ai import LLMClient
from src.ingest.job_details_extractor import JobDetails
from src.ingest.job_searcher import JobSearchResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoringResult:
    """Result of the relevance scoring analysis."""

    score: int
    matching_skills: List[str]
    missing_skills: List[str]
    reasoning: str
    required_experience_years: Optional[int] = None


class RelevanceScorer:
    """Scores job listings against a user resume using AI."""

    def __init__(self, llm_client: LLMClient, user_experience_years: Optional[int] = None):
        """
        Initialize the RelevanceScorer.

        Args:
            llm_client: An instance of LLMClient to use for analysis.
            user_experience_years: Maximum years of experience candidate has.
        """
        self.llm = llm_client
        self.user_experience_years = user_experience_years

    def _extract_experience_regex(self, text: Optional[str]) -> Optional[int]:
        """Attempt to extract required years of experience using regex."""
        if not text:
            return None
        # matches: "5+ years", "3-5 years", "2 yrs" followed optionally by "of experience"
        pattern = r"(\d{1,2})(?:\s*\+)?\s*(?:to\s*\d{1,2}\s*)?(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)\s*(?:of\s*)?(?:[\w\s]{0,20})?(?:experience|exp)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def score_job(self, resume_text: str, job_details: JobDetails) -> Optional[ScoringResult]:
        """
        Analyzes the relevance of a job to the user's resume.

        Args:
            resume_text: Raw text extracted from the user's resume.
            job_details: Detailed information about the job.

        Returns:
            ScoringResult if successful, None otherwise.
        """
        extracted_exp = self._extract_experience_regex(job_details.description)

        # 1. Regex pre-filtering for experience
        if extracted_exp is not None and self.user_experience_years is not None:
            if extracted_exp > self.user_experience_years:
                logger.info(
                    f"Regex filter caught job '{job_details.title}': strictly requires {extracted_exp} years, candidate has {self.user_experience_years}."
                )
                return ScoringResult(
                    score=0,
                    matching_skills=[],
                    missing_skills=["Required Experience"],
                    reasoning=f"Regex filter: Job requires {extracted_exp}+ years of experience, but candidate has a maximum of {self.user_experience_years} years.",
                    required_experience_years=extracted_exp,
                )

        prompt = self._construct_prompt(resume_text, job_details)
        system_instruction = (
            "You are an expert career coach and technical recruiter. "
            "Analyze the job description against the resume provided. "
            "Be objective and critical. Provide high-quality feedback."
        )

        try:
            logger.info(f"Scoring job '{job_details.title}' at '{job_details.company}'")
            json_response = self.llm.generate_json(prompt, system_instruction=system_instruction)

            if not json_response:
                logger.error("Empty JSON response from LLM during scoring.")
                return None

            return ScoringResult(
                score=int(json_response.get("score", 0)),
                matching_skills=json_response.get("matching_skills", []),
                missing_skills=json_response.get("missing_skills", []),
                reasoning=json_response.get("reasoning", ""),
                required_experience_years=json_response.get("required_experience_years", extracted_exp),
            )
        except Exception as e:
            logger.error(f"Error during relevance scoring: {e}")
            return None

    def _construct_prompt(self, resume_text: str, job_details: JobDetails) -> str:
        """Constructs the prompt for the LLM."""
        prompt = f"""
Analyze the suitability of this candidate for the following job.

### Resume Content:
{resume_text}

### Job Title:
{job_details.title}

### Company:
{job_details.company}

### Job Description:
{job_details.description}
"""
        if self.user_experience_years is not None:
            prompt += f"\n### Candidate Experience Context:\nIMPORTANT: The candidate has a maximum of **{self.user_experience_years} years** of professional experience. If the job explicitly requires strictly MORE than {self.user_experience_years} years of overall experience (e.g., requires 5+ years but the candidate has {self.user_experience_years}), the candidate is unqualified. Heavily penalize the score (score < 30).\n"

        prompt += """
### Evaluation Criteria:
1. **Score (0-100)**: How well do the candidate's skills and experience align with the job requirements?
2. **Matching Skills**: List 3-7 key technical or soft skills found in both the resume and the job.
3. **Missing Skills**: List 3-7 key requirements from the job that are missing or weak in the resume.
4. **Reasoning**: Provide a 2-3 sentence explanation for the score.
5. **Required Experience (Years)**: The minimum years of experience categorically strictly required by the job (integer). Return 0 if not explicitly mentioned.

### Output Format:
Provide the result ONLY as a raw JSON object with these keys:
- "score": integer
- "matching_skills": list of strings
- "missing_skills": list of strings
- "reasoning": string
- "required_experience_years": integer
"""
        return prompt


class FastScorer:
    """Performs rapid keyword-based scoring without LLM calls."""

    def __init__(self, keywords: List[str]):
        """
        Initialize with a list of target keywords.

        Args:
            keywords: List of skills or technologies to match.
        """
        self.keywords = [k.lower() for k in keywords]

    def score_result(self, result: JobSearchResult) -> int:
        """
        Calculates a simple overlap score for a search result.

        Args:
            result: The JobSearchResult to score.

        Returns:
            int: A score from 0-100 based on keyword density in title.
        """
        if not self.keywords:
            return 0

        title = result.title.lower()
        matches = sum(1 for kw in self.keywords if kw in title)

        # Title matches are weighted heavily
        score = (matches / len(self.keywords)) * 100
        # Boost if title contains exact matches for key skills
        if matches > 0:
            score = min(100, score + 20)

        return int(score)
