from src.core.network_graph import Connection, ConnectionMetadata
from src.core.relevance_scorer import ScoringResult
from src.generator.template_manager import TemplateManager
from src.ingest.job_details_extractor import JobDetails


def test_render_job():
    job = JobDetails(
        id="123",
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        description="Write code.",
        posted_date="2023-10-01",
        seniority_level="Senior",
        employment_type="Full-time",
        job_function="Engineering",
        industries="Technology",
        link="http://example.com",
    )
    score = ScoringResult(
        score=85,
        matching_skills=["Python", "AWS"],
        missing_skills=["Kubernetes"],
        reasoning="Good match",
    )

    manager = TemplateManager()
    output = manager.render_job(job, score)

    assert "# Software Engineer @ [[Tech_Corp]]" in output
    assert "**Score:** 85/100" in output
    assert "- Python" in output
    assert "- Kubernetes" in output
    assert "Write code." in output
    assert "**Location:** Remote" in output


def test_render_company():
    manager = TemplateManager()
    output = manager.render_company(
        name="Tech Corp",
        industry="Software",
        location="San Francisco",
        website="http://techcorp.com",
        jobs=[{"title": "DevOps", "filename": "Job_123", "status": "#ToApply"}],
        people=[{"name": "Alice", "filename": "Person_Alice", "title": "CTO"}],
    )

    assert "# Tech Corp" in output
    assert "**Industry:** Software" in output
    assert "[[Job_123|DevOps]] (#ToApply)" in output
    assert "[[Person_Alice|Alice]] - CTO" in output


def test_render_person():
    meta = ConnectionMetadata(last_contacted="2023-01-01", notes="Nice person")
    person = Connection(
        first_name="Bob",
        last_name="Smith",
        company="Tech Corp",
        position="Developer",
        connected_on="2022-05-01",
        metadata=meta,
    )

    manager = TemplateManager()
    output = manager.render_person(person)

    assert "# Bob Smith" in output
    assert "**Title:** Developer" in output
    assert "**Company:** [[Tech_Corp]]" in output
    assert "Nice person" in output
