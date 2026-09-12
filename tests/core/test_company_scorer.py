import pytest
from src.core.company_scorer import CompanyScorer
from src.core.network_graph import Connection


@pytest.fixture
def scorer():
    config = {
        "search": {
            "external_sites": [
                {"company": "OpenAI", "url": "https://openai.com/careers"},
                {"company": "Rearc", "url": "https://rearc.io"},
            ],
            "target_companies": ["Anthropic"],
        }
    }
    return CompanyScorer(config)


def test_scorer_target_company(scorer):
    jobs = [
        {
            "id": "j1",
            "title": "AI Engineer",
            "relevance_score": 85,
            "status": "new",
            "description": "LLM agentic workflows",
        },
        {
            "id": "j2",
            "title": "GenAI Specialist",
            "relevance_score": 80,
            "status": "new",
            "description": "Transformers and RAG",
        },
    ]
    conns = [
        Connection(
            first_name="Shubham",
            last_name="K",
            company="Rearc",
            position="Talent Acquisition Lead",
            connected_on="2024-01-01",
        ),
    ]

    eval_result = scorer.score_company("Rearc", jobs, conns)
    assert eval_result.name == "Rearc"
    assert eval_result.target_tier == "Target"
    assert eval_result.job_fit_score >= 85
    assert eval_result.company_fit_score >= 90
    assert eval_result.network_score >= 40
    assert eval_result.score >= 80
    assert eval_result.key_connection_count == 1
    assert eval_result.key_contacts[0]["role_type"] == "talent"


def test_scorer_zero_network_high_job_fit(scorer):
    jobs = [
        {
            "id": "j1",
            "title": "Machine Learning Engineer",
            "relevance_score": 88,
            "status": "new",
            "description": "Deep learning models",
        },
    ]
    conns = []

    eval_result = scorer.score_company("Stripe", jobs, conns)
    assert eval_result.network_score == 0
    assert eval_result.job_fit_score == 88
    # Composite should be positive and heavily guided by job and company fit
    assert eval_result.score >= 50
    assert eval_result.connection_count == 0


def test_scorer_legacy_service_penalty(scorer):
    jobs = [
        {
            "id": "j1",
            "title": "Java Developer",
            "relevance_score": 40,
            "status": "new",
            "description": "IT Staffing and staff augmentation",
        },
    ]
    conns = [
        Connection(
            first_name="John",
            last_name="Doe",
            company="Acme Staffing",
            position="Consultant",
            connected_on="2023-01-01",
        ),
    ]

    eval_result = scorer.score_company("Acme Staffing", jobs, conns)
    assert eval_result.job_fit_score == 40
    assert eval_result.company_fit_score <= 50
    assert eval_result.score < 50
