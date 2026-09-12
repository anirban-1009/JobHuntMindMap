from src.core.company_clusterer import CompanyClusterer
from src.core.company_scorer import CompanyEvaluation


def test_cluster_warm_outreach():
    ev = CompanyEvaluation(
        id="rearc",
        name="Rearc",
        score=85,
        job_fit_score=85,
        company_fit_score=90,
        network_score=50,
        job_count=2,
        high_match_job_count=2,
        max_job_score=85,
        avg_job_score=82.5,
        connection_count=1,
        key_connection_count=1,
        target_tier="Target",
        key_contacts=[{"name": "Shubham K", "title": "Talent Acquisition Lead", "role_type": "talent"}],
    )
    cluster, action = CompanyClusterer.assign_action_cluster(ev)
    assert cluster == "Warm Outreach"
    assert "Shubham K" in action
    assert "referral" in action.lower()


def test_cluster_direct_apply():
    ev = CompanyEvaluation(
        id="anthropic",
        name="Anthropic",
        score=75,
        job_fit_score=90,
        company_fit_score=95,
        network_score=0,
        job_count=3,
        high_match_job_count=3,
        max_job_score=90,
        avg_job_score=88.0,
        connection_count=0,
        key_connection_count=0,
        target_tier="Target",
    )
    cluster, action = CompanyClusterer.assign_action_cluster(ev)
    assert cluster == "Direct Apply"
    assert "directly" in action.lower()


def test_cluster_network_nurture():
    ev = CompanyEvaluation(
        id="google",
        name="Google",
        score=55,
        job_fit_score=50,
        company_fit_score=80,
        network_score=60,
        job_count=1,
        high_match_job_count=0,
        max_job_score=50,
        avg_job_score=50.0,
        connection_count=5,
        key_connection_count=3,
        target_tier="Standard",
    )
    cluster, action = CompanyClusterer.assign_action_cluster(ev)
    assert cluster == "Network Nurture"
    assert "informational" in action.lower() or "keep in touch" in action.lower()


def test_assign_domain_cluster():
    jobs_genai = [
        {"title": "GenAI Engineer", "description": "Working with LLMs and prompt engineering, RAG pipelines."},
    ]
    domain = CompanyClusterer.assign_domain_cluster("Anthropic", jobs_genai)
    assert domain == "Generative AI & LLMs"

    jobs_cv = [
        {"title": "Computer Vision Researcher", "description": "Object detection and PyTorch deep learning."},
    ]
    domain_cv = CompanyClusterer.assign_domain_cluster("Waymo", jobs_cv)
    assert domain_cv == "Core ML & Computer Vision"
