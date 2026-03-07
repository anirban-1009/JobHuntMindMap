import pytest

from src.core.database import DatabaseManager


class TestDatabaseManager:
    @pytest.fixture
    def db(self, tmp_path):
        # Use a temporary file for testing
        db_file = tmp_path / "test_jobs.db"
        return DatabaseManager(db_path=str(db_file))

    def test_init_db(self, db):
        """Verify fallback tables are created."""
        with db._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            assert "jobs" in tables
            assert "requests" in tables

    def test_save_and_get_job(self, db):
        """Test saving and retrieving a job."""
        job_data = {
            "id": "job123",
            "title": "AI Engineer",
            "company": "DeepMind",
            "location": "London",
            "description": "Building AGi",
            "status": "new",
        }
        db.save_job(job_data)

        retrieved = db.get_job("job123")
        assert retrieved is not None
        assert retrieved["title"] == "AI Engineer"
        assert retrieved["company"] == "DeepMind"

    def test_job_exists(self, db):
        """Test job_exists method."""
        job_data = {"id": "exists123", "title": "Test"}
        db.save_job(job_data)

        assert db.job_exists("exists123") is True
        assert db.job_exists("missing123") is False

    def test_get_all_jobs(self, db):
        """Test retrieving multiple jobs."""
        db.save_job({"id": "j1", "title": "Job 1"})
        db.save_job({"id": "j2", "title": "Job 2"})

        jobs = db.get_all_jobs()
        assert len(jobs) == 2
        ids = [j["id"] for j in jobs]
        assert "j1" in ids
        assert "j2" in ids

    def test_save_and_get_request(self, db):
        """Test referral request storage."""
        db.save_job({"id": "ref123", "title": "Referral Job"})
        db.save_request(
            job_id="ref123",
            connection_name="John Doe",
            profile_url="http://linkedin/john",
            message="Hi John, can you refer me?",
        )

        requests = db.get_requests_for_job("ref123")
        assert len(requests) == 1
        assert requests[0]["connection_name"] == "John Doe"
        assert requests[0]["message_content"] == "Hi John, can you refer me?"

    def test_get_jobs_by_status(self, db):
        """Test filtering jobs by status."""
        db.save_job({"id": "s1", "title": "Job 1", "status": "new"})
        db.save_job({"id": "s2", "title": "Job 2", "status": "applied"})

        new_jobs = db.get_jobs_by_status("new")
        assert len(new_jobs) == 1
        assert new_jobs[0]["id"] == "s1"

        applied_jobs = db.get_jobs_by_status("applied")
        assert len(applied_jobs) == 1
        assert applied_jobs[0]["id"] == "s2"

    def test_get_all_requests(self, db):
        """Test retrieving all referral requests."""
        db.save_job({"id": "r1", "title": "Job 1"})
        db.save_job({"id": "r2", "title": "Job 2"})
        db.save_request("r1", "Alice", "url1", "msg1")
        db.save_request("r2", "Bob", "url2", "msg2")

        all_reqs = db.get_all_requests()
        assert len(all_reqs) == 2

    def test_save_analysis(self, db):
        """Test updating job with analysis results."""
        db.save_job({"id": "a1", "title": "Job 1"})
        db.save_analysis("a1", 85, '{"reason": "good"}')

        job = db.get_job("a1")
        assert job["relevance_score"] == 85
        assert job["analysis_data"] == '{"reason": "good"}'

    def test_update_job_status(self, db):
        """Test updating job status."""
        db.save_job({"id": "status1", "title": "Job 1", "status": "new"})
        db.update_job_status("status1", "interviewing")

        job = db.get_job("status1")
        assert job["status"] == "interviewing"

    def test_get_all_analyses(self, db):
        """Test retrieving jobs with analysis data."""
        db.save_job({"id": "an1", "title": "Job 1"})
        db.save_job({"id": "an2", "title": "Job 2"})
        db.save_analysis("an1", 90, '{"data": 1}')

        analyses = db.get_all_analyses(min_score=80)
        assert len(analyses) == 1
        assert analyses[0]["id"] == "an1"

        none = db.get_all_analyses(min_score=95)
        assert len(none) == 0

    def test_delete_job(self, db):
        """Test deleting a job and its associated requests."""
        db.save_job({"id": "del1", "title": "Job 1"})
        db.save_request("del1", "Alice", "url", "msg")

        db.delete_job("del1")

        assert db.get_job("del1") is None
        assert len(db.get_requests_for_job("del1")) == 0
