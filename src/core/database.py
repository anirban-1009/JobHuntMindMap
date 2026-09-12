import contextlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None


class DatabaseManager:
    """Manages SQLite database interactions."""

    def __init__(self, db_path: str = "data/jobs.db", embedding_dim: int = 768):
        """
        Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file.
            embedding_dim: Dimensionality of vault search embeddings (must match the
                configured embedding model; changing it requires a full reindex).
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_dim = embedding_dim
        self.vector_search_enabled = sqlite_vec is not None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Creates and returns a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        if self.vector_search_enabled:
            try:
                conn.enable_load_extension(True)
                sqlite_vec.load(conn)
                conn.enable_load_extension(False)
            except Exception as e:
                logger.warning(f"sqlite-vec extension failed to load; semantic search disabled: {e}")
                self.vector_search_enabled = False
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
            specialization TEXT DEFAULT 'General',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new',
            applied_at TIMESTAMP
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
            conn = self._get_connection()
            try:
                conn.execute(create_jobs_table)

                # Migrate: add columns that didn't exist in older DBs (CREATE TABLE IF NOT
                # EXISTS above only helps on a fresh DB).
                existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)")}
                if "applied_at" not in existing_columns:
                    conn.execute("ALTER TABLE jobs ADD COLUMN applied_at TIMESTAMP")

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

                # Create companies table
                create_companies_table = """
                CREATE TABLE IF NOT EXISTS companies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    action_cluster TEXT,
                    domain_cluster TEXT,
                    job_count INTEGER DEFAULT 0,
                    high_match_job_count INTEGER DEFAULT 0,
                    max_job_score INTEGER DEFAULT 0,
                    avg_job_score REAL DEFAULT 0,
                    connection_count INTEGER DEFAULT 0,
                    key_connection_count INTEGER DEFAULT 0,
                    target_tier TEXT,
                    status TEXT DEFAULT 'new',
                    outreach_poc TEXT,
                    outreach_date TEXT,
                    evaluation_data TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
                conn.execute(create_companies_table)

                # Add trigger for companies timestamp
                create_companies_trigger = """
                CREATE TRIGGER IF NOT EXISTS update_companies_timestamp 
                AFTER UPDATE ON companies
                BEGIN
                    UPDATE companies SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END;
                """
                conn.execute(create_companies_trigger)

                conn.execute(create_trigger)

                # Full-text index over the generated Obsidian vault (job/person/company notes
                # and any freeform notes added directly in Obsidian).
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS vault_index USING fts5(
                        path UNINDEXED, category UNINDEXED, title, content
                    );
                    """
                )

                # Tracks mtime separately for text vs. embedding indexing, since a document can be
                # text-reindexed (cheap, no LLM call) without also being re-embedded (needs an LLM
                # call) - without this, a text-only reindex would make a changed file look
                # "up to date" and permanently mask it from ever being (re-)embedded.
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS vault_index_meta (
                        path TEXT PRIMARY KEY,
                        mtime REAL NOT NULL,
                        embedded_mtime REAL
                    );
                    """
                )

                if self.vector_search_enabled:
                    conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS vault_vector_map (
                            path TEXT PRIMARY KEY,
                            vec_rowid INTEGER NOT NULL
                        );
                        """
                    )
                    conn.execute(
                        f"""
                        CREATE VIRTUAL TABLE IF NOT EXISTS vault_vectors USING vec0(
                            embedding float[{self.embedding_dim}]
                        );
                        """
                    )

                conn.commit()
            finally:
                conn.close()
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
            relevance_score, analysis_data, specialization
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?
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
        status=CASE 
            WHEN jobs.status = 'discovered' THEN excluded.status 
            ELSE jobs.status 
        END,
        relevance_score=COALESCE(excluded.relevance_score, jobs.relevance_score),
            analysis_data=COALESCE(excluded.analysis_data, jobs.analysis_data),
            specialization=excluded.specialization,
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
            job_data.get("specialization", "General"),
        )

        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, params)
        except Exception as e:
            logger.error(f"Failed to save job {job_data.get('id')}: {e}")
            raise

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a job by ID."""
        query = "SELECT * FROM jobs WHERE id = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
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
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, (limit, offset))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get jobs: {e}")
            return []

    def get_jobs_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Retrieves jobs filtered by status."""
        query = "SELECT * FROM jobs WHERE status = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, (status,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get jobs by status {status}: {e}")
            return []

    def job_exists(self, job_id: str) -> bool:
        """Checks if a job exists in the database."""
        query = "SELECT 1 FROM jobs WHERE id = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
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
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, (job_id, connection_name, profile_url, message))
        except Exception as e:
            logger.error(f"Failed to save request for job {job_id}: {e}")
            raise

    def get_requests_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Retrieves requests for a specific job."""
        query = "SELECT * FROM requests WHERE job_id = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, (job_id,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get requests for job {job_id}: {e}")
            return []

    def get_all_requests(self) -> List[Dict[str, Any]]:
        """Retrieves all referral requests."""
        query = "SELECT * FROM requests"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get all requests: {e}")
            return []

    def save_analysis(self, job_id: str, score: int, analysis_data: str):
        """Updates a job with analysis results."""
        query = "UPDATE jobs SET relevance_score = ?, analysis_data = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, (score, analysis_data, job_id))
                logger.info(f"Saved analysis for job {job_id}.")
        except Exception as e:
            logger.error(f"Failed to save analysis for job {job_id}: {e}")
            raise

    def update_job_status(self, job_id: str, status: str):
        """Updates the status of a job.

        Stamps `applied_at` the moment a job transitions to 'applied', and clears it if the
        job is reverted back to 'to_apply' - so it always reflects the most recent application.
        """
        if status == "applied":
            query = "UPDATE jobs SET status = ?, applied_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        elif status == "to_apply":
            query = "UPDATE jobs SET status = ?, applied_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        else:
            query = "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, (status, job_id))
                logger.info(f"Updated status for job {job_id} to {status}.")
        except Exception as e:
            logger.error(f"Failed to update status for job {job_id}: {e}")
            raise

    def get_all_analyses(self, min_score: int = 0) -> List[Dict[str, Any]]:
        """Retrieves all jobs that have analysis data."""
        query = "SELECT id, relevance_score, analysis_data FROM jobs WHERE analysis_data IS NOT NULL AND relevance_score >= ?"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, (min_score,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get analyses: {e}")
            return []

    def get_vault_index_status(self) -> Dict[str, Dict[str, Optional[float]]]:
        """Returns {path: {"mtime": ..., "embedded_mtime": ...}} for every indexed vault file."""
        query = "SELECT path, mtime, embedded_mtime FROM vault_index_meta"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query)
                return {
                    row["path"]: {"mtime": row["mtime"], "embedded_mtime": row["embedded_mtime"]}
                    for row in cursor.fetchall()
                }
        except Exception as e:
            logger.error(f"Failed to get vault index status: {e}")
            return {}

    def upsert_vault_document(
        self,
        path: str,
        category: str,
        title: str,
        content: str,
        mtime: float,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """
        Indexes (or re-indexes) a single vault document for text search, and for semantic
        search if an embedding is provided and sqlite-vec is available. Passing no embedding
        updates text search only and leaves any previously stored embedding untouched.
        """
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute("DELETE FROM vault_index WHERE path = ?", (path,))
                    conn.execute(
                        "INSERT INTO vault_index (path, category, title, content) VALUES (?, ?, ?, ?)",
                        (path, category, title, content),
                    )

                    existing_meta = conn.execute(
                        "SELECT embedded_mtime FROM vault_index_meta WHERE path = ?", (path,)
                    ).fetchone()
                    embedded_mtime = existing_meta["embedded_mtime"] if existing_meta else None

                    if self.vector_search_enabled and embedding:
                        existing_vec = conn.execute(
                            "SELECT vec_rowid FROM vault_vector_map WHERE path = ?", (path,)
                        ).fetchone()
                        if existing_vec:
                            conn.execute("DELETE FROM vault_vectors WHERE rowid = ?", (existing_vec["vec_rowid"],))

                        cursor = conn.execute(
                            "INSERT INTO vault_vectors (embedding) VALUES (?)",
                            (sqlite_vec.serialize_float32(embedding),),
                        )
                        vec_rowid = cursor.lastrowid
                        conn.execute(
                            """
                            INSERT INTO vault_vector_map (path, vec_rowid) VALUES (?, ?)
                            ON CONFLICT(path) DO UPDATE SET vec_rowid = excluded.vec_rowid
                            """,
                            (path, vec_rowid),
                        )
                        embedded_mtime = mtime

                    conn.execute(
                        """
                        INSERT INTO vault_index_meta (path, mtime, embedded_mtime) VALUES (?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET mtime = excluded.mtime, embedded_mtime = excluded.embedded_mtime
                        """,
                        (path, mtime, embedded_mtime),
                    )
        except Exception as e:
            logger.error(f"Failed to index vault document {path}: {e}")
            raise

    def delete_vault_document(self, path: str) -> None:
        """Removes a vault document from the text and semantic indexes."""
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute("DELETE FROM vault_index WHERE path = ?", (path,))
                    conn.execute("DELETE FROM vault_index_meta WHERE path = ?", (path,))
                    if self.vector_search_enabled:
                        existing = conn.execute(
                            "SELECT vec_rowid FROM vault_vector_map WHERE path = ?", (path,)
                        ).fetchone()
                        if existing:
                            conn.execute("DELETE FROM vault_vectors WHERE rowid = ?", (existing["vec_rowid"],))
                            conn.execute("DELETE FROM vault_vector_map WHERE path = ?", (path,))
        except Exception as e:
            logger.error(f"Failed to delete vault document {path}: {e}")
            raise

    def search_vault_text(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search over the vault index using FTS5, ranked by BM25."""
        sql = """
        SELECT path, category, title,
               snippet(vault_index, 3, '**', '**', '…', 12) AS snippet,
               bm25(vault_index) AS rank
        FROM vault_index WHERE vault_index MATCH ? ORDER BY rank LIMIT ?
        """
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(sql, (query, limit))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Vault text search failed for query '{query}': {e}")
            return []

    def search_vault_semantic(self, embedding: List[float], limit: int = 10) -> List[Dict[str, Any]]:
        """K-nearest-neighbor search over vault document embeddings via sqlite-vec."""
        if not self.vector_search_enabled:
            return []

        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT rowid, distance FROM vault_vectors WHERE embedding MATCH ? AND k = ? ORDER BY distance",
                    (sqlite_vec.serialize_float32(embedding), limit),
                )
                neighbors = cursor.fetchall()
                if not neighbors:
                    return []

                rowid_to_distance = {row["rowid"]: row["distance"] for row in neighbors}
                placeholders = ",".join("?" * len(rowid_to_distance))
                map_rows = conn.execute(
                    f"SELECT path, vec_rowid FROM vault_vector_map WHERE vec_rowid IN ({placeholders})",
                    list(rowid_to_distance.keys()),
                ).fetchall()

                results = []
                for m in map_rows:
                    meta = conn.execute(
                        "SELECT category, title FROM vault_index WHERE path = ? LIMIT 1", (m["path"],)
                    ).fetchone()
                    results.append(
                        {
                            "path": m["path"],
                            "distance": rowid_to_distance[m["vec_rowid"]],
                            "category": meta["category"] if meta else None,
                            "title": meta["title"] if meta else None,
                        }
                    )
                results.sort(key=lambda r: r["distance"])
                return results
        except Exception as e:
            logger.error(f"Vault semantic search failed: {e}")
            return []

    def delete_job(self, job_id: str):
        """Deletes a job and its associated requests from the database."""
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute("DELETE FROM requests WHERE job_id = ?", (job_id,))
                    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
                logger.info(f"Deleted job {job_id} and its associated requests.")
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            raise

    def save_company(self, company_data: Dict[str, Any]):
        """
        Saves or updates a company evaluation in the database.

        Args:
            company_data: Dictionary containing company evaluation details.
        """
        query = """
        INSERT INTO companies (
            id, name, score, action_cluster, domain_cluster,
            job_count, high_match_job_count, max_job_score, avg_job_score,
            connection_count, key_connection_count, target_tier,
            status, outreach_poc, outreach_date, evaluation_data, notes
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?
        )
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            score=excluded.score,
            action_cluster=excluded.action_cluster,
            domain_cluster=excluded.domain_cluster,
            job_count=excluded.job_count,
            high_match_job_count=excluded.high_match_job_count,
            max_job_score=excluded.max_job_score,
            avg_job_score=excluded.avg_job_score,
            connection_count=excluded.connection_count,
            key_connection_count=excluded.key_connection_count,
            target_tier=excluded.target_tier,
            status=CASE WHEN companies.status != 'new' THEN companies.status ELSE excluded.status END,
            outreach_poc=COALESCE(companies.outreach_poc, excluded.outreach_poc),
            outreach_date=COALESCE(companies.outreach_date, excluded.outreach_date),
            evaluation_data=excluded.evaluation_data,
            notes=COALESCE(companies.notes, excluded.notes),
            updated_at=CURRENT_TIMESTAMP
        """
        eval_data_str = ""
        if "evaluation_data" in company_data and company_data["evaluation_data"]:
            if isinstance(company_data["evaluation_data"], (dict, list)):
                eval_data_str = json.dumps(company_data["evaluation_data"])
            else:
                eval_data_str = str(company_data["evaluation_data"])

        params = (
            company_data.get("id"),
            company_data.get("name"),
            company_data.get("score", 0),
            company_data.get("action_cluster", "Watchlist"),
            company_data.get("domain_cluster", "General Tech"),
            company_data.get("job_count", 0),
            company_data.get("high_match_job_count", 0),
            company_data.get("max_job_score", 0),
            company_data.get("avg_job_score", 0.0),
            company_data.get("connection_count", 0),
            company_data.get("key_connection_count", 0),
            company_data.get("target_tier", "Standard"),
            company_data.get("status", "new"),
            company_data.get("outreach_poc"),
            company_data.get("outreach_date"),
            eval_data_str,
            company_data.get("notes"),
        )

        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, params)
        except Exception as e:
            logger.error(f"Failed to save company {company_data.get('name')}: {e}")
            raise

    def get_company(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Retrieves a company by ID or exact/case-insensitive name."""
        query = "SELECT * FROM companies WHERE id = ? OR LOWER(name) = LOWER(?)"
        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, (identifier, identifier))
                row = cursor.fetchone()
                if row:
                    res = dict(row)
                    if res.get("evaluation_data"):
                        try:
                            res["evaluation_data"] = json.loads(res["evaluation_data"])
                        except Exception:
                            pass
                    return res
                return None
        except Exception as e:
            logger.error(f"Failed to get company {identifier}: {e}")
            return None

    def get_all_companies(
        self,
        min_score: int = 0,
        action_cluster: Optional[str] = None,
        domain_cluster: Optional[str] = None,
        sort_by: str = "score",
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Retrieves evaluated companies with filtering and sorting."""
        sort_column_map = {
            "score": "score DESC, max_job_score DESC, connection_count DESC",
            "jobs": "job_count DESC, high_match_job_count DESC, score DESC",
            "network": "connection_count DESC, key_connection_count DESC, score DESC",
            "name": "name ASC",
        }
        order_by = sort_column_map.get(sort_by, "score DESC")

        conditions = ["score >= ?"]
        params: List[Any] = [min_score]

        if action_cluster and action_cluster.lower() != "all":
            conditions.append("LOWER(action_cluster) LIKE ?")
            params.append(f"%{action_cluster.lower()}%")

        if domain_cluster and domain_cluster.lower() != "all":
            conditions.append("LOWER(domain_cluster) LIKE ?")
            params.append(f"%{domain_cluster.lower()}%")

        where_clause = " WHERE " + " AND ".join(conditions)
        query = f"SELECT * FROM companies{where_clause} ORDER BY {order_by} LIMIT ?"
        params.append(limit)

        try:
            with contextlib.closing(self._get_connection()) as conn:
                cursor = conn.execute(query, tuple(params))
                results = []
                for row in cursor.fetchall():
                    c_dict = dict(row)
                    if c_dict.get("evaluation_data"):
                        try:
                            c_dict["evaluation_data"] = json.loads(c_dict["evaluation_data"])
                        except Exception:
                            pass
                    results.append(c_dict)
                return results
        except Exception as e:
            logger.error(f"Failed to get companies: {e}")
            return []

    def update_company_status(
        self, company_id: str, status: str, outreach_poc: Optional[str] = None, notes: Optional[str] = None
    ):
        """Updates company outreach/application status."""
        query = """
        UPDATE companies
        SET status = ?,
            outreach_poc = COALESCE(?, outreach_poc),
            outreach_date = CASE WHEN ? IS NOT NULL THEN CURRENT_TIMESTAMP ELSE outreach_date END,
            notes = COALESCE(?, notes),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ? OR LOWER(name) = LOWER(?)
        """
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(query, (status, outreach_poc, outreach_poc, notes, company_id, company_id))
                logger.info(f"Updated status for company {company_id} to {status}.")
        except Exception as e:
            logger.error(f"Failed to update company status for {company_id}: {e}")
            raise

    def delete_company(self, company_id: str):
        """Deletes a company evaluation from the database."""
        try:
            with contextlib.closing(self._get_connection()) as conn:
                with conn:
                    conn.execute(
                        "DELETE FROM companies WHERE id = ? OR LOWER(name) = LOWER(?)", (company_id, company_id)
                    )
                logger.info(f"Deleted company {company_id}.")
        except Exception as e:
            logger.error(f"Failed to delete company {company_id}: {e}")
            raise
