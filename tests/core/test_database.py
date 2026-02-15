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
