import pytest
from src.core.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_file = tmp_path / "test_jobs.db"
    return DatabaseManager(str(db_file))


def test_save_and_get_company(db):
    company_data = {
        "id": "test_corp",
        "name": "Test Corp",
        "score": 85,
        "action_cluster": "Warm Outreach",
        "domain_cluster": "Generative AI & LLMs",
        "job_count": 5,
        "high_match_job_count": 3,
        "max_job_score": 90,
        "avg_job_score": 82.5,
        "connection_count": 2,
        "key_connection_count": 1,
        "target_tier": "Target",
        "status": "new",
        "evaluation_data": {"job_fit_score": 90, "company_fit_score": 85, "network_score": 70},
    }
    db.save_company(company_data)

    retrieved = db.get_company("test_corp")
    assert retrieved is not None
    assert retrieved["name"] == "Test Corp"
    assert retrieved["score"] == 85
    assert retrieved["action_cluster"] == "Warm Outreach"
    assert retrieved["evaluation_data"]["job_fit_score"] == 90

    # Test retrieval by case-insensitive name
    by_name = db.get_company("test corp")
    assert by_name is not None
    assert by_name["id"] == "test_corp"


def test_get_all_companies_filtering_and_sorting(db):
    c1 = {"id": "c1", "name": "Company A", "score": 90, "action_cluster": "Warm Outreach"}
    c2 = {"id": "c2", "name": "Company B", "score": 75, "action_cluster": "Direct Apply"}
    c3 = {"id": "c3", "name": "Company C", "score": 50, "action_cluster": "Watchlist"}
    db.save_company(c1)
    db.save_company(c2)
    db.save_company(c3)

    all_c = db.get_all_companies(min_score=60)
    assert len(all_c) == 2
    assert all_c[0]["name"] == "Company A"
    assert all_c[1]["name"] == "Company B"

    warm_c = db.get_all_companies(action_cluster="warm")
    assert len(warm_c) == 1
    assert warm_c[0]["name"] == "Company A"


def test_update_and_delete_company(db):
    company_data = {"id": "target_co", "name": "Target Co", "score": 80, "status": "new"}
    db.save_company(company_data)

    db.update_company_status("target_co", "outreach_sent", outreach_poc="Jane Doe", notes="Referral requested")
    updated = db.get_company("target_co")
    assert updated["status"] == "outreach_sent"
    assert updated["outreach_poc"] == "Jane Doe"
    assert updated["notes"] == "Referral requested"

    db.delete_company("target_co")
    assert db.get_company("target_co") is None
