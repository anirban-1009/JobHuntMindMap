from unittest.mock import MagicMock
from src.core.search_expansion import SearchExpansionService


def test_generate_expanded_queries_basic():
    """Verify that the service generates new queries and doesn't duplicate existing ones."""
    mock_llm = MagicMock()
    # Mock generate_json to return a specific set of queries
    mock_llm.generate_json.return_value = {"expanded_queries": ["AI Engineer", "ML Systems Engineer", "LLM Researcher"]}

    service = SearchExpansionService(mock_llm)
    resume_text = "Experienced in Python and PyTorch."
    current_keywords = ["AI Engineer"]

    expanded = service.generate_expanded_queries(resume_text, current_keywords)

    # "AI Engineer" should be filtered out as it is already in current_keywords
    assert "ML Systems Engineer" in expanded
    assert "LLM Researcher" in expanded
    assert "AI Engineer" not in expanded
    assert len(expanded) == 2


def test_generate_expanded_queries_with_top_jobs():
    """Verify that top jobs context is passed to the LLM prompt."""
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {"expanded_queries": ["Specific Role"]}

    service = SearchExpansionService(mock_llm)
    top_jobs = [{"title": "MLOps Engineer", "company": "TechCo", "reasoning": "Strong infra skills"}]

    service.generate_expanded_queries("Resume text", ["AI"], top_jobs=top_jobs)

    # Check that the prompt sent to the LLM contains information from top_jobs
    args, kwargs = mock_llm.generate_json.call_args
    prompt = args[0]
    assert "MLOps Engineer" in prompt
    assert "TechCo" in prompt
    assert "Strong infra skills" in prompt


def test_generate_expanded_queries_error_handling():
    """Verify that the service returns an empty list if the LLM call fails."""
    mock_llm = MagicMock()
    mock_llm.generate_json.side_effect = Exception("API Error")

    service = SearchExpansionService(mock_llm)
    expanded = service.generate_expanded_queries("Resume", ["AI"])

    assert expanded == []
