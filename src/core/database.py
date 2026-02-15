import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages SQLite database interactions."""

    def __init__(self, db_path: str = "data/jobs.db"):
        """
        Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates and returns a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the database schema."""
        create_jobs_table = """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            description TEXT,
            posted_date TEXT,
            seniority_level TEXT,
            employment_type TEXT,
            job_function TEXT,
            industries TEXT,
            link TEXT,
            salary TEXT,
            apply_link TEXT,
            raw_data TEXT,
            relevance_score INTEGER,
            analysis_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new'
        );
        """

        # Add trigger to update updated_at
        create_trigger = """
        CREATE TRIGGER IF NOT EXISTS update_jobs_timestamp 
        AFTER UPDATE ON jobs
        BEGIN
            UPDATE jobs SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
        END;
        """

        try:
            with self._get_connection() as conn:
                conn.execute(create_jobs_table)

                # Create requests table
                create_requests_table = """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    connection_name TEXT,
                    connection_profile_url TEXT,
                    status TEXT DEFAULT 'pending',
                    message_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                );
                """
                conn.execute(create_requests_table)

                # Add trigger for requests timestamp
                create_requests_trigger = """
                CREATE TRIGGER IF NOT EXISTS update_requests_timestamp 
                AFTER UPDATE ON requests
                BEGIN
                    UPDATE requests SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END;
                """
                conn.execute(create_requests_trigger)

                conn.execute(create_trigger)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_job(self, job_data: Dict[str, Any]):
        """
        Saves or updates a job in the database.

        Args:
            job_data: Dictionary containing job details.
        """
        query = """
        INSERT INTO jobs (
            id, title, company, location, description, posted_date,
            seniority_level, employment_type, job_function, industries,
            link, salary, apply_link, raw_data, status,
            relevance_score, analysis_data
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            company=excluded.company,
            location=excluded.location,
            description=excluded.description,
            posted_date=excluded.posted_date,
            seniority_level=excluded.seniority_level,
            employment_type=excluded.employment_type,
            job_function=excluded.job_function,
            industries=excluded.industries,
            link=excluded.link,
            salary=excluded.salary,
            apply_link=excluded.apply_link,
            raw_data=excluded.raw_data,
            relevance_score=COALESCE(excluded.relevance_score, jobs.relevance_score),
            analysis_data=COALESCE(excluded.analysis_data, jobs.analysis_data),
            updated_at=CURRENT_TIMESTAMP
        """

        # Serialize raw_data if present
        raw_data_str = ""
        if "raw_data" in job_data and job_data["raw_data"]:
            if isinstance(job_data["raw_data"], (dict, list)):
                raw_data_str = json.dumps(job_data["raw_data"])
            else:
                raw_data_str = str(job_data["raw_data"])

        params = (
            job_data.get("id"),
            job_data.get("title"),
            job_data.get("company"),
            job_data.get("location"),
            job_data.get("description"),
            job_data.get("posted_date"),
            job_data.get("seniority_level"),
            job_data.get("employment_type"),
            job_data.get("job_function"),
            job_data.get("industries"),
            job_data.get("link"),
            job_data.get("salary"),
            job_data.get("apply_link"),
            raw_data_str,
            job_data.get("status", "new"),
            job_data.get("relevance_score"),
            job_data.get("analysis_data"),
        )

        try:
            with self._get_connection() as conn:
                conn.execute(query, params)
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save job {job_data.get('id')}: {e}")
            raise

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a job by ID."""
        query = "SELECT * FROM jobs WHERE id = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, (job_id,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    def get_all_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all jobs with pagination."""
        query = "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ? OFFSET ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, (limit, offset))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get jobs: {e}")
            return []

    def job_exists(self, job_id: str) -> bool:
        """Checks if a job exists in the database."""
        query = "SELECT 1 FROM jobs WHERE id = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, (job_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check job existence {job_id}: {e}")
            return False

    def save_request(self, job_id: str, connection_name: str, profile_url: str, message: str):
        """Saves a referral request."""
        query = """
        INSERT INTO requests (job_id, connection_name, connection_profile_url, message_content)
        VALUES (?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                conn.execute(query, (job_id, connection_name, profile_url, message))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save request for job {job_id}: {e}")
            raise

    def get_requests_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Retrieves requests for a specific job."""
        query = "SELECT * FROM requests WHERE job_id = ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, (job_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get requests for job {job_id}: {e}")
            return []

    def save_analysis(self, job_id: str, score: int, analysis_data: str):
        """Updates a job with analysis results."""
        query = "UPDATE jobs SET relevance_score = ?, analysis_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            with self._get_connection() as conn:
                conn.execute(query, (score, analysis_data, job_id))
                conn.commit()
                logger.info(f"Saved analysis for job {job_id}.")
        except Exception as e:
            logger.error(f"Failed to save analysis for job {job_id}: {e}")
            raise

    def get_all_analyses(self, min_score: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all jobs that have analysis data."""
        query = "SELECT id, relevance_score, analysis_data FROM jobs WHERE analysis_data IS NOT NULL AND relevance_score >= ?"
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(query, (min_score,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get analyses: {e}")
            return []
