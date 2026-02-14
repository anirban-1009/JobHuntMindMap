import json
import pathlib
import sys
from dataclasses import asdict
from types import SimpleNamespace
from typing import Any, Dict, Optional

import click
import yaml
from colorama import Fore, init

from src.core.ai import get_llm_client
from src.core.gap_analysis import GapAnalyzer
from src.core.network_graph import NetworkGraphBuilder
from src.core.relevance_scorer import RelevanceScorer, ScoringResult
from src.generator.sync_service import SyncService
from src.ingest.browser_manager import BrowserManager
from src.ingest.job_details_extractor import JobDetailsExtractor
from src.ingest.job_searcher import JobSearcher
from src.ingest.resume_parser import PDFResumeParser
from src.notification.email_service import EmailService

init(autoreset=True)


class MindMapApp:
    """Main application controller for the Job Hunt Mindmap tool."""

    def __init__(self, config_path: str):
        """
        Initialize the application with configuration.

        Args:
            config_path: Path to the configuration YAML file.
        """
        self.config_path = pathlib.Path(config_path)
        self.config: Dict[str, Any] = self._load_config()
        self.session_path = pathlib.Path("data/session.json")

    def _load_config(self) -> Dict[str, Any]:
        """Loads and validates the configuration file."""
        if not self.config_path.exists():
            click.echo(Fore.RED + f"Config file not found: {self.config_path}")
            sys.exit(1)
        with open(self.config_path, "r") as f:
            try:
                return yaml.safe_load(f)
            except yaml.YAMLError as e:
                click.echo(Fore.RED + f"Error parsing YAML: {e}")
                sys.exit(1)

    def check_env(self) -> None:
        """Validates the environment and configuration."""
        click.echo(Fore.CYAN + "Checking environment...")
        # Self._load_config already validates existence and YAML syntax
        click.echo(Fore.GREEN + "Config file valid.")
        click.echo(Fore.GREEN + "Mindmap is ready to run!")

    def login(self) -> None:
        """Starts a browser session for manual login to LinkedIn."""
        click.echo(Fore.CYAN + f"Starting browser for manual login (session saved to {self.session_path})...")
        try:
            with BrowserManager(headless=False, session_path=self.session_path) as browser:
                browser.login_manual()
                click.echo(Fore.GREEN + "Exiting login mode.")
        except Exception as e:
            click.echo(Fore.RED + f"Login failed: {e}")
            sys.exit(1)

    def search(self, headless: bool) -> None:
        """Performs a job search on LinkedIn."""
        click.echo(Fore.CYAN + f"Starting job search (headless={headless})...")
        try:
            with BrowserManager(headless=headless, session_path=self.session_path) as browser:
                searcher = JobSearcher(browser)
                search_cfg = self.config.get("search", {})
                keywords_list = search_cfg.get("keywords", [])
                location = search_cfg.get("location", "United States")
                location_type = search_cfg.get("location_type", "Any")
                filters = search_cfg.get("filters", {})

                all_results = []
                for keywords in keywords_list:
                    click.echo(f"Searching for '{keywords}' in {location}...")
                    results = searcher.search(keywords, location, filters, location_type)
                    all_results.extend(results)
                    click.echo(Fore.GREEN + f"Found {len(results)} jobs.")

                unique_results = {r.id: r for r in all_results if r.id}.values()
                click.echo(Fore.CYAN + f"\nTotal unique jobs found: {len(unique_results)}")
                for r in list(unique_results)[:10]:
                    click.echo(f"- {Fore.WHITE}{r.title} {Fore.YELLOW}@ {r.company} {Fore.BLUE}({r.location})")
        except Exception as e:
            click.echo(Fore.RED + f"Search failed: {e}")
            sys.exit(1)

    def scrape(self, headless: bool, limit: Optional[int], force: bool) -> None:
        """Scrapes detailed information for jobs."""
        ai_cfg = self.config.get("ai", {})
        click.echo(Fore.CYAN + f"Starting job extraction (headless={headless})...")
        try:
            llm = get_llm_client(ai_cfg)
            with BrowserManager(headless=headless, session_path=self.session_path) as browser:
                searcher = JobSearcher(browser)
                extractor = JobDetailsExtractor(browser, llm_client=llm)

                search_cfg = self.config.get("search", {})
                all_results = []
                for keywords in search_cfg.get("keywords", []):
                    results = searcher.search(
                        keywords,
                        search_cfg.get("location", "United States"),
                        search_cfg.get("filters", {}),
                        search_cfg.get("location_type", "Any"),
                    )
                    all_results.extend(results)

                unique_results = list({r.id: r for r in all_results if r.id}.values())
                if limit:
                    unique_results = unique_results[:limit]

                click.echo(Fore.CYAN + f"\nScraping details for {len(unique_results)} jobs...")
                details = extractor.extract_multiple_jobs(unique_results, force=force)
                click.echo(Fore.GREEN + f"Successfully scraped {len(details)} / {len(unique_results)} jobs.")
        except Exception as e:
            click.echo(Fore.RED + f"Scrape failed: {e}")
            sys.exit(1)

    def test_ai(self, prompt: str) -> None:
        """Tests the connection to the AI provider."""
        ai_cfg = self.config.get("ai", {})
        provider = ai_cfg.get("provider", "gemini")
        click.echo(Fore.CYAN + f"Initializing {provider} client and sending test prompt...")
        try:
            client = get_llm_client(ai_cfg)
            response = client.generate(prompt)
            if response:
                click.echo(Fore.GREEN + f"\nAI Response ({provider}):")
                click.echo(f"{Fore.WHITE}{response.strip()}")
            else:
                click.echo(Fore.RED + "\nAI returned empty response. Check API key/Ollama.")
        except Exception as e:
            click.echo(Fore.RED + f"\nAI Check failed: {e}")
            sys.exit(1)

    def find_network(self, job_id: str) -> None:
        """Finds professional connections for a given job ID."""
        user_cfg = self.config.get("user", {})
        conn_path = user_cfg.get("linkedin_connections_path") or self.config.get("network", {}).get("connections_path")
        connections_path = pathlib.Path(conn_path or "data/Connections.csv")

        if not connections_path.exists():
            connections_path = pathlib.Path("data/sample_connections.csv")
            if not connections_path.exists():
                click.echo(Fore.RED + "Connections file not found.")
                sys.exit(1)

        try:
            extractor = JobDetailsExtractor(None)
            job = extractor.get_cached_job(job_id)
            if not job:
                click.echo(Fore.RED + f"Job {job_id} not found in cache. Run 'scrape' first.")
                sys.exit(1)

            builder = NetworkGraphBuilder(connections_path, metadata_path=user_cfg.get("linkedin_metadata_path"))
            matches = builder.find_matches(job)

            click.echo(Fore.CYAN + f"\nFound {len(matches)} connections at {job.company}:")
            for conn in matches:
                click.echo(f"- {Fore.WHITE}{conn.full_name} {Fore.YELLOW}({conn.position})")
        except Exception as e:
            click.echo(Fore.RED + f"Network analysis failed: {e}")
            sys.exit(1)

    def score_jobs(self, score_all: bool, job_id: Optional[str]) -> None:
        """Scores jobs against the user's resume."""
        user_cfg = self.config.get("user", {})
        resume_path = pathlib.Path(user_cfg.get("resume_path", "data/resume.pdf"))
        if not resume_path.exists():
            resume_path = pathlib.Path("data/sample_resume.pdf")
            if not resume_path.exists():
                click.echo(Fore.RED + "Resume not found.")
                sys.exit(1)

        try:
            resume_parser = PDFResumeParser()
            resume_text = resume_parser.extract_text(resume_path)
            llm = get_llm_client(self.config.get("ai", {}))
            scorer = RelevanceScorer(llm)
            extractor = JobDetailsExtractor(None)

            jobs_to_score = []
            skipped_count = 0

            if job_id:
                job = extractor.get_cached_job(job_id)
                if job:
                    jobs_to_score.append(job)
            elif score_all:
                for f in extractor.cache_dir.glob("*.json"):
                    if "_" not in f.stem and f.stem.isdigit():
                        # Check if analysis already exists
                        analysis_path = extractor.cache_dir / f"{f.stem}_analysis.json"
                        if analysis_path.exists():
                            skipped_count += 1
                            continue

                        job = extractor.get_cached_job(f.stem)
                        if job:
                            jobs_to_score.append(job)

            if skipped_count > 0:
                click.echo(Fore.YELLOW + f"Skipping {skipped_count} already scored jobs.")

            click.echo(Fore.CYAN + f"Scoring {len(jobs_to_score)} jobs...")
            for job in jobs_to_score:
                result = scorer.score_job(resume_text, job)
                if result:
                    output_path = extractor.cache_dir / f"{job.id}_analysis.json"
                    with open(output_path, "w") as f:
                        json.dump(asdict(result), f, indent=2)
                    color = Fore.GREEN if result.score >= 70 else Fore.YELLOW if result.score >= 40 else Fore.RED
                    click.echo(f"Job {job.id}: {color}Score {result.score}{Fore.RESET} - {result.reasoning}")
        except Exception as e:
            click.echo(Fore.RED + f"Scoring failed: {e}")
            sys.exit(1)

    def analyze_gaps(self, min_score: int) -> None:
        """Analyzes skill gaps across scored jobs."""
        try:
            llm = get_llm_client(self.config.get("ai", {}))
            analyzer = GapAnalyzer(llm)
            cache_dir = pathlib.Path("data/job_cache")
            results = []
            for f in cache_dir.glob("*_analysis.json"):
                with open(f, "r") as jf:
                    data = json.load(jf)
                    res = ScoringResult(**data)
                    if res.score >= min_score:
                        results.append(res)

            if not results:
                click.echo(Fore.YELLOW + "No scored jobs found.")
                return

            click.echo(Fore.CYAN + f"Analyzing gaps across {len(results)} jobs...")
            gap_result = analyzer.analyze_gaps(results)
            if gap_result:
                click.echo(Fore.GREEN + "\n=== Top Missing Skills ===")
                for skill, count in gap_result.skill_frequency.items():
                    click.echo(f"- {skill}: {count} jobs")
                click.echo(Fore.CYAN + "\n=== Improvement Plan ===")
                click.echo(gap_result.improvement_plan)
        except Exception as e:
            click.echo(Fore.RED + f"Gap analysis failed: {e}")
            sys.exit(1)

    def notify(self, min_score: int) -> None:
        """Sends an email digest of high-scoring jobs."""
        try:
            extractor = JobDetailsExtractor(None)
            cache_dir = pathlib.Path("data/job_cache")
            scored_jobs = []
            for f in cache_dir.glob("*_analysis.json"):
                with open(f, "r") as jf:
                    score_data = json.load(jf)
                    if score_data.get("score", 0) >= min_score:
                        job_id = f.stem.replace("_analysis", "")
                        job = extractor.get_cached_job(job_id)
                        if job:
                            scored_jobs.append({"job": job, "score": SimpleNamespace(**score_data)})

            if not scored_jobs:
                click.echo(Fore.YELLOW + "No high-scoring jobs to notify.")
                return

            click.echo(Fore.CYAN + f"Sending digest for {len(scored_jobs)} jobs...")
            service = EmailService(self.config)
            if service.send_job_digest(scored_jobs):
                click.echo(Fore.GREEN + "Notifications sent successfully.")
            else:
                click.echo(Fore.RED + "Failed to send notifications.")
        except Exception as e:
            click.echo(Fore.RED + f"Notification failed: {e}")
            sys.exit(1)

    def sync(self) -> None:
        """Syncs all data to Obsidian."""
        click.echo(Fore.CYAN + "Syncing with Obsidian...")
        try:
            syncer = SyncService(self.config)
            syncer.sync()
            click.echo(Fore.GREEN + "Sync complete!")
        except Exception as e:
            click.echo(Fore.RED + f"Sync failed: {e}")
            sys.exit(1)


@click.group()
def cli():
    """Job Hunt Mindmap CLI"""
    from dotenv import load_dotenv

    from src.utils.logger import setup_logging

    load_dotenv()
    setup_logging()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def check(config):
    """Validate configuration and environment."""
    app = MindMapApp(config)
    app.check_env()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def login(config):
    """Obtain LinkedIn session cookies manually."""
    app = MindMapApp(config)
    app.login()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
def search(config, headless):
    """Search for jobs based on configuration."""
    app = MindMapApp(config)
    app.search(headless)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs")
@click.option("--force", is_flag=True, default=False, help="Force re-scrape")
def scrape(config, headless, limit, force):
    """Scrape details for found jobs."""
    app = MindMapApp(config)
    app.scrape(headless, limit, force)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--prompt", default="Say 'Mindmap AI Online'", help="Test prompt")
def test_ai(config, prompt):
    """Test AI provider connection."""
    app = MindMapApp(config)
    app.test_ai(prompt)


@cli.command()
@click.argument("job_id")
@click.option("--config", default="config.yaml", help="Path to config file")
def network(job_id, config):
    """Find connections for a job."""
    app = MindMapApp(config)
    app.find_network(job_id)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--all", "score_all", is_flag=True, default=False, help="Score all jobs")
@click.argument("job_id", required=False)
def score(config, score_all, job_id):
    """Score jobs against resume."""
    app = MindMapApp(config)
    app.score_jobs(score_all, job_id)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--min-score", default=0, help="Min score for analysis")
def analyze_gaps(config, min_score):
    """Analyze skill gaps."""
    app = MindMapApp(config)
    app.analyze_gaps(min_score)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--min-score", default=70, help="Min score for digest")
def notify(config, min_score):
    """Send job digest email."""
    app = MindMapApp(config)
    app.notify(min_score)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.argument("job_id")
def tailor(config, job_id):
    """Generate a tailored resume for a specific job."""
    from src.core.ai import get_llm_client
    from src.generator.resume_tailorer import ResumeTailorer
    from src.ingest.job_details_extractor import JobDetailsExtractor
    from src.ingest.resume_parser import PDFResumeParser

    app = MindMapApp(config)

    # 1. Load Job Details
    extractor = JobDetailsExtractor(None)
    job = extractor.get_cached_job(job_id)
    if not job:
        click.echo(Fore.RED + f"Job {job_id} not found in cache.")
        sys.exit(1)

    # 2. Extract Resume Data
    resume_json_path = pathlib.Path("data/resume.json")

    # Try to auto-create JSON from PDF if missing
    if not resume_json_path.exists():
        pdf_path_str = app.config.get("user", {}).get("resume_path")
        pdf_path = pathlib.Path(pdf_path_str) if pdf_path_str else None

        if pdf_path and pdf_path.exists():
            click.echo(Fore.CYAN + f"Parsing resume PDF from {pdf_path} to create structured data...")
            try:
                parser = PDFResumeParser()
                resume_text = parser.parse(pdf_path)

                # Use LLM to structure this text
                llm = get_llm_client(app.config.get("ai", app.config))
                prompt = f"""
                You are a data extraction assistant. Convert the following Resume Text into a valid JSON object matching this structure:
                {{
                  "first_name": "String", "last_name": "String", "email": "String", "phone": "String",
                  "linkedin": "String (URL)", "github": "String (URL)", "website": "String (URL)",
                  "job_title": "String", "professional_summary": "String",
                  "experience": [ {{"title": "String", "company": "String", "dates": "String", "location": "String", "bullets": ["String"]}} ],
                  "education": [ {{"institution": "String", "degree": "String", "dates": "String", "location": "String", "description": "String"}} ],
                  "skills": {{ "Category": ["Skill"] }}
                }}
                
                RESUME TEXT:
                {resume_text[:4000]}
                
                Return ONLY valid JSON.
                """
                json_str = llm.generate(prompt)

                # Clean markdown blocks
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0].strip()
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0].strip()

                resume_data = json.loads(json_str)

                with open(resume_json_path, "w") as f:
                    json.dump(resume_data, f, indent=2)
                click.echo(Fore.GREEN + "Successfully created 'data/resume.json' from PDF.")

            except Exception as e:
                click.echo(Fore.YELLOW + f"Failed to auto-parse PDF: {e}. Falling back to sample.")

    if not resume_json_path.exists():
        click.echo(Fore.RED + "Structured resume data not found at data/resume.json.")

        # Create a sample template if missing
        sample_data = {
            "first_name": "First",
            "last_name": "Last",
            "email": "email@example.com",
            "phone": "555-123-4567",
            "linkedin": "linkedin.com/in/user",
            "github": "github.com/user",
            "website": "example.com",
            "job_title": "Software Engineer",
            "professional_summary": "Experienced engineer...",
            "experience": [
                {
                    "title": "Software Developer",
                    "company": "Tech Corp",
                    "dates": "2020-Present",
                    "location": "San Francisco, CA",
                    "bullets": ["Implemented X using Python.", "Improved performance by Y%."],
                }
            ],
            "education": [
                {
                    "institution": "University of Tech",
                    "degree": "B.S. Computer Science",
                    "dates": "2016-2020",
                    "location": "City, State",
                    "description": "Graduated with Honors.",
                }
            ],
            "skills": {"Languages": ["Python", "JavaScript"], "Tools": ["Docker", "Git"]},
        }
        with open(resume_json_path, "w") as f:
            json.dump(sample_data, f, indent=2)
        click.echo(
            Fore.YELLOW
            + "Created sample 'data/resume.json'. Please fill it with your details and run this command again."
        )
        sys.exit(1)

    with open(resume_json_path, "r") as f:
        resume_data = json.load(f)

    # 3. Tailor
    tailorer = ResumeTailorer(app.config)
    click.echo(Fore.CYAN + f"Tailoring resume for {job.title} at {job.company}...")

    # Construct description from title + description
    job_desc = f"Title: {job.title}\nCompany: {job.company}\n\n{job.description}"
    tailored_data = tailorer.tailor_resume(resume_data, job_desc)

    # 4. Generate PDF
    try:
        latex = tailorer.generate_latex(tailored_data)
        output_dir = pathlib.Path("output/resumes")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Clean company name for filename
        safe_company = "".join(c for c in job.company if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        output_path = output_dir / f"Resume_{safe_company}_{job_id}.pdf"

        tailorer.compile_pdf(latex, output_path)
        click.echo(Fore.GREEN + f"Tailored resume saved to: {output_path}")
    except Exception as e:
        click.echo(Fore.RED + f"Failed to generate PDF: {e}")
        # Save LaTeX for debugging
        if "latex" in locals():
            debug_tex = pathlib.Path("output/resumes") / f"debug_{job_id}.tex"
            with open(debug_tex, "w") as f:
                f.write(latex)
            click.echo(Fore.YELLOW + f"Saved LaTeX source to {debug_tex} for manual compilation.")


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def sync(config):
    """Sync data to Obsidian vault."""
    app = MindMapApp(config)
    app.sync()


if __name__ == "__main__":
    cli()
