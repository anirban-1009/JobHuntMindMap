from typing import List, Dict, Any, Optional
from src.core.ai.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SearchExpansionService:
    """
    Analyzes the user's profile and existing successful job matches
    to generate new, evolved search queries.
    """

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_expanded_queries(
        self, resume_text: str, current_keywords: List[str], top_jobs: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Generates new search keywords by evolving existing ones
        based on resume and successful matches.
        """
        logger.info("Generating expanded search queries...")

        jobs_context = ""
        if top_jobs:
            jobs_context = "\n".join(
                [f"- {j.get('title')} @ {j.get('company')}: {j.get('reasoning', 'No reasoning')}" for j in top_jobs[:5]]
            )

        prompt = f"""
Analyze the following candidate profile and current search strategy to generate new, high-probability search queries.

### Resume Content:
{resume_text}

### Current Search Keywords:
{", ".join(current_keywords)}

### Successful Matches (Jobs the candidate liked/scored high):
{jobs_context if jobs_context else "No high-scoring jobs yet."}

### Task:
Generate 10 new, distinct search queries. Include:
1. **Semantic Variations**: Different ways to name the same role (e.g., "AI Engineer" -> "ML Systems Engineer").
2. **Adjacent Roles**: Roles that require similar skills but have different titles (e.g., "LLM Engineer" -> "Search Infrastructure Engineer").
3. **Niche Specializations**: More specific versions of the roles based on the resume's unique strengths.
4. **Industry-Specific Terms**: Keywords used by top-tier companies in the candidate's target sector.

### Output Format:
Provide the result ONLY as a raw JSON object:
{{
  "expanded_queries": ["query 1", "query 2", ...]
}}
"""
        system_instruction = "You are an expert technical recruiter specializing in AI/ML talent acquisition."

        try:
            response = self.llm.generate_json(prompt, system_instruction=system_instruction)
            queries = response.get("expanded_queries", [])

            # Deduplicate against current keywords
            filtered_queries = [q for q in queries if q.lower() not in [ck.lower() for ck in current_keywords]]

            logger.info(f"Generated {len(filtered_queries)} new search queries.")
            return filtered_queries
        except Exception as e:
            logger.error(f"Error generating expanded queries: {e}")
            return []
