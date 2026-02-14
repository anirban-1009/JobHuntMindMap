from dataclasses import dataclass
from typing import List, Optional

from src.core.ai import LLMClient
from src.ingest.job_details_extractor import JobDetails
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoringResult:
    """Result of the relevance scoring analysis."""

    score: int
    matching_skills: List[str]
    missing_skills: List[str]
    reasoning: str


class RelevanceScorer:
    """Scores job listings against a user resume using AI."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize the RelevanceScorer.

        Args:
            llm_client: An instance of LLMClient to use for analysis.
        """
        self.llm = llm_client

    def score_job(self, resume_text: str, job_details: JobDetails) -> Optional[ScoringResult]:
        """
        Analyzes the relevance of a job to the user's resume.

        Args:
            resume_text: Raw text extracted from the user's resume.
            job_details: Detailed information about the job.

        Returns:
            ScoringResult if successful, None otherwise.
        """
        logger.info(f"Scoring job '{job_details.title}' at '{job_details.company}'")

        # Try up to 3 times with progressively stricter prompting
        max_retries = 3
        for attempt in range(max_retries):
            try:
                prompt = self._construct_prompt(resume_text, job_details, attempt)
                system_instruction = (
                    "You are an expert career coach and technical recruiter. "
                    "Analyze the job description against the resume provided. "
                    "Be objective and critical. Provide high-quality feedback. "
                    "CRITICAL: Respond ONLY with valid JSON. No markdown, no explanations, just JSON."
                )

                json_response = self.llm.generate_json(prompt, system_instruction=system_instruction)

                if not json_response:
                    if attempt < max_retries - 1:
                        logger.warning(f"Empty JSON response (attempt {attempt + 1}/{max_retries}). Retrying...")
                        continue
                    else:
                        logger.error("Empty JSON response from LLM after all retries.")
                        return self._create_fallback_result(job_details)

                # Validate required fields
                if "score" not in json_response or "reasoning" not in json_response:
                    if attempt < max_retries - 1:
                        logger.warning(f"Incomplete JSON response (attempt {attempt + 1}/{max_retries}). Retrying...")
                        continue
                    else:
                        logger.error("Incomplete JSON response after all retries.")
                        return self._create_fallback_result(job_details)

                return ScoringResult(
                    score=int(json_response.get("score", 0)),
                    matching_skills=json_response.get("matching_skills", []),
                    missing_skills=json_response.get("missing_skills", []),
                    reasoning=json_response.get("reasoning", ""),
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Error during relevance scoring (attempt {attempt + 1}/{max_retries}): {e}. Retrying..."
                    )
                    continue
                else:
                    logger.error(f"Error during relevance scoring after all retries: {e}")
                    return self._create_fallback_result(job_details)

        return self._create_fallback_result(job_details)

    def _create_fallback_result(self, job_details: JobDetails) -> ScoringResult:
        """Creates a default result when LLM scoring fails."""
        return ScoringResult(
            score=0,
            matching_skills=[],
            missing_skills=["Unable to analyze - LLM scoring failed"],
            reasoning=f"Failed to score this job automatically. Please review manually: {job_details.title} at {job_details.company}",
        )

    def _construct_prompt(self, resume_text: str, job_details: JobDetails, attempt: int = 0) -> str:
        """Constructs the prompt for the LLM."""

        # Truncate resume and job description if too long to avoid context overflow
        max_resume_length = 2000
        max_desc_length = 1500

        resume_excerpt = resume_text[:max_resume_length] + ("..." if len(resume_text) > max_resume_length else "")
        job_desc_excerpt = job_details.description[:max_desc_length] + (
            "..." if len(job_details.description) > max_desc_length else ""
        )

        # For retries, be EXTREMELY explicit
        if attempt > 0:
            return f"""CRITICAL: Your last response was invalid. Respond with PURE JSON ONLY.

DO NOT use ```json or ``` markdown.
DO NOT add any text before or after the JSON.
START your response with {{ and END with }}

Analyze this candidate:

RESUME: {resume_excerpt}

JOB: {job_details.title} at {job_details.company}
DESCRIPTION: {job_desc_excerpt}

Respond with THIS EXACT FORMAT (fill in your values):
{{"score": 80, "matching_skills": ["skill1", "skill2", "skill3"], "missing_skills": ["gap1", "gap2"], "reasoning": "Brief explanation here"}}"""

        # First attempt - clear but friendly
        return f"""IMPORTANT: You must respond with ONLY a valid JSON object. No markdown, no code blocks, no explanations.

Analyze this candidate's resume against the job requirements and provide a JSON response.

RESUME:
{resume_excerpt}

JOB TITLE: {job_details.title}
COMPANY: {job_details.company}

JOB DESCRIPTION:
{job_desc_excerpt}

Evaluate:
1. Score (0-100): Overall match between resume and job requirements
2. Matching Skills: 3-7 skills present in both resume and job
3. Missing Skills: 3-7 key job requirements missing from resume  
4. Reasoning: 2-3 sentences explaining the score

RESPONSE FORMAT - Copy this structure exactly:
{{"score": 75, "matching_skills": ["Python", "REST APIs", "Docker"], "missing_skills": ["Kubernetes", "GraphQL"], "reasoning": "Strong backend experience with Python and APIs. Missing some modern DevOps tools."}}

Your response (JSON only, no markdown):"""
