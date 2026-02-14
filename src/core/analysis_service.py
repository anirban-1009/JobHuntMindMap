import json
import pathlib
from dataclasses import asdict
from typing import Any, List, Optional

from src.core.ai import LLMClient
from src.core.gap_analysis import GapAnalyzer
from src.core.relevance_scorer import RelevanceScorer, ScoringResult
from src.ingest.job_details_extractor import JobDetails, JobDetailsExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AnalysisService:
    """Orchestrates job scoring and gap analysis."""

    def __init__(self, llm_client: LLMClient):
        """
        Initialize the AnalysisService.

        Args:
            llm_client: LLM client for analysis.
        """
        self.llm = llm_client
        self.scorer = RelevanceScorer(llm_client)
        self.gap_analyzer = GapAnalyzer(llm_client)
        self.extractor = JobDetailsExtractor(None)
        self.cache_dir = pathlib.Path("data/job_cache")

    def score_job(self, job: JobDetails, resume_text: str) -> Optional[ScoringResult]:
        """Scores a single job and saves the analysis."""
        result = self.scorer.score_job(resume_text, job)
        if result:
            output_path = self.cache_dir / f"{job.id}_analysis.json"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(asdict(result), f, indent=2)
            return result
        return None

    def score_all_cached_jobs(self, resume_text: str) -> List[tuple[JobDetails, ScoringResult]]:
        """Scores all jobs found in the cache."""
        scored = []
        for f in self.cache_dir.glob("*.json"):
            if "_" not in f.stem and f.stem.isdigit():
                job = self.extractor.get_cached_job(f.stem)
                if job:
                    result = self.score_job(job, resume_text)
                    if result:
                        scored.append((job, result))
        return scored

    def run_gap_analysis(self, min_score: int) -> Any:
        """Runs gap analysis across high-scoring jobs."""
        results = []
        for f in self.cache_dir.glob("*_analysis.json"):
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                    res = ScoringResult(**data)
                    if res.score >= min_score:
                        results.append(res)
            except Exception as e:
                logger.warning(f"Failed to load analysis {f}: {e}")

        if not results:
            return None

        return self.gap_analyzer.analyze_gaps(results)
