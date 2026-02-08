import pathlib
import sys
from typing import Optional

import click
import yaml
from colorama import Fore, init

init(autoreset=True)


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
    click.echo(Fore.CYAN + "Checking environment...")

    # Check Config
    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        try:
            yaml.safe_load(f)
            click.echo(Fore.GREEN + "Config file valid.")
        except yaml.YAMLError as e:
            click.echo(Fore.RED + f"Error parsing YAML: {e}")
            sys.exit(1)

    click.echo(Fore.GREEN + "Mindmap is ready to run!")


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def login(config):
    """Obtain LinkedIn session cookies manually."""
    from src.ingest.browser_manager import BrowserManager

    # Path to store session - hardcoded for now or from config?
    # Ideally should be from config, but let's default to a sane location.
    # Or load config to get it? The user's goal is just "test the implementation".
    session_path = pathlib.Path("data/session.json")

    click.echo(Fore.CYAN + f"Starting browser for manual login (session will be saved to {session_path})...")

    try:
        # Force headless=False so user can see
        with BrowserManager(headless=False, session_path=session_path) as browser:
            browser.login_manual()
            click.echo(Fore.GREEN + "Exiting login mode.")

    except Exception as e:
        click.echo(Fore.RED + f"Login failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
def search(config: str, headless: bool):
    """
    Search for jobs on LinkedIn based on the configuration file.

    Args:
        config (str): Path to the config.yaml file.
        headless (bool): Whether to run the browser in headless mode.
    """
    from src.ingest.browser_manager import BrowserManager
    from src.ingest.job_searcher import JobSearcher

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    session_path = pathlib.Path("data/session.json")
    if not session_path.exists():
        click.echo(Fore.YELLOW + "Warning: session.json not found. You might need to run 'login' first.")

    click.echo(Fore.CYAN + f"Starting job search (headless={headless})...")

    try:
        with BrowserManager(headless=headless, session_path=session_path) as browser:
            searcher = JobSearcher(browser)

            search_cfg = cfg.get("search", {})
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

            # deduplicate by ID
            unique_results = {r.id: r for r in all_results if r.id}.values()

            click.echo(Fore.CYAN + f"\nTotal unique jobs found: {len(unique_results)}")
            for r in list(unique_results)[:10]:  # Show first 10
                click.echo(f"- {Fore.WHITE}{r.title} {Fore.YELLOW}@ {r.company} {Fore.BLUE}({r.location})")

    except Exception as e:
        click.echo(Fore.RED + f"Search failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs to scrape")
@click.option("--force", is_flag=True, default=False, help="Force re-scrape of cached jobs")
def scrape(config: str, headless: bool, limit: Optional[int], force: bool):
    """
    Scrape full details for jobs found in search.

    Args:
        config (str): Path to the config.yaml file.
        headless (bool): Whether to run the browser in headless mode.
        limit (int): Optional limit on number of jobs.
        force (bool): Whether to force re-scrape.
    """
    from src.core.ai import get_llm_client
    from src.ingest.browser_manager import BrowserManager
    from src.ingest.job_details_extractor import JobDetailsExtractor
    from src.ingest.job_searcher import JobSearcher

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    session_path = pathlib.Path("data/session.json")
    ai_cfg = cfg.get("ai", {})

    click.echo(Fore.CYAN + f"Starting job search and extraction (headless={headless})...")

    try:
        llm = get_llm_client(ai_cfg)
        with BrowserManager(headless=headless, session_path=session_path) as browser:
            searcher = JobSearcher(browser)
            extractor = JobDetailsExtractor(browser, llm_client=llm)

            search_cfg = cfg.get("search", {})
            keywords_list = search_cfg.get("keywords", [])
            location = search_cfg.get("location", "United States")
            location_type = search_cfg.get("location_type", "Any")
            filters = search_cfg.get("filters", {})

            all_results = []
            for keywords in keywords_list:
                click.echo(f"Searching for '{keywords}' in {location}...")
                results = searcher.search(keywords, location, filters, location_type)
                all_results.extend(results)

            # deduplicate by ID
            unique_results = list({r.id: r for r in all_results if r.id}.values())

            if limit:
                unique_results = unique_results[:limit]

            click.echo(Fore.CYAN + f"\nScraping details for {len(unique_results)} unique jobs...")

            # Using extractor to get details
            details = extractor.extract_multiple_jobs(unique_results, force=force)

            click.echo(Fore.GREEN + f"Successfully scraped {len(details)} / {len(unique_results)} jobs.")

            # Print a few
            for d in details[:5]:
                click.echo(f"- {Fore.WHITE}{d.title} {Fore.YELLOW}@ {d.company}")
                click.echo(f"  {Fore.BLUE}Link: {d.link}")

    except Exception as e:
        click.echo(Fore.RED + f"Scrape failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--prompt", default="Say 'Mindmap AI Online' if you can hear me.", help="Test prompt")
def test_ai(config: str, prompt: str):
    """Test AI provider connection."""
    from src.core.llm_client import get_llm_client

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        try:
            cfg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            click.echo(Fore.RED + f"Error parsing YAML: {e}")
            sys.exit(1)

    ai_cfg = cfg.get("ai", {})
    provider = ai_cfg.get("provider", "gemini")

    click.echo(Fore.CYAN + f"Initializing {provider} client...")

    try:
        client = get_llm_client(ai_cfg)
        click.echo(Fore.CYAN + f"Sending test prompt: '{prompt}'")
        response = client.generate(prompt)

        if response:
            click.echo(Fore.GREEN + f"\nAI Response ({provider}):")
            click.echo(f"{Fore.WHITE}{response.strip()}")
        else:
            click.echo(Fore.RED + "\nAI returned an empty response. Check your API key or Ollama status.")

    except Exception as e:
        click.echo(Fore.RED + f"\nAI Check failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("job_id")
@click.option("--config", default="config.yaml", help="Path to config file")
def network(job_id: str, config: str):
    """Find connections at a specific job's company."""
    from src.core.network_graph import NetworkGraphBuilder
    from src.ingest.job_details_extractor import JobDetailsExtractor

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    # Resolve connections path from config or common locations
    user_cfg = cfg.get("user", {})
    connections_path = user_cfg.get("linkedin_connections_path") or cfg.get("network", {}).get("connections_path")

    if connections_path:
        connections_path = pathlib.Path(connections_path)
    else:
        connections_path = pathlib.Path("data/Connections.csv")

    if not connections_path.exists():
        # Try sample if original missing
        connections_path = pathlib.Path("data/sample_connections.csv")
        if not connections_path.exists():
            click.echo(Fore.RED + "Connections file not found.")
            sys.exit(1)

    try:
        extractor = JobDetailsExtractor(None)  # No browser needed for cache loading
        job = extractor.get_cached_job(job_id)

        if not job:
            click.echo(Fore.RED + f"Job {job_id} not found in cache. Run 'scrape' first.")
            sys.exit(1)

        metadata_path = user_cfg.get("linkedin_metadata_path")
        if metadata_path:
            metadata_path = pathlib.Path(metadata_path)

        builder = NetworkGraphBuilder(connections_path, metadata_path=metadata_path)
        matches = builder.find_matches(job)

        click.echo(Fore.CYAN + f"\nFound {len(matches)} connections at {job.company}:")
        for conn in matches:
            click.echo(f"- {Fore.WHITE}{conn.full_name} {Fore.YELLOW}({conn.position})")
            if conn.metadata.last_contacted:
                click.echo(f"  {Fore.BLUE}Last Contacted: {conn.metadata.last_contacted}")
            if conn.metadata.achievements:
                click.echo(f"  {Fore.BLUE}Achievements: {', '.join(conn.metadata.achievements)}")

    except Exception as e:
        click.echo(Fore.RED + f"Network analysis failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--all", "score_all", is_flag=True, default=False, help="Score all cached jobs")
@click.argument("job_id", required=False)
def score(config: str, score_all: bool, job_id: Optional[str]):
    """
    Score jobs against your resume.

    You must provide either a JOB_ID or use --all.
    """
    import json
    from dataclasses import asdict

    from src.core.ai import get_llm_client
    from src.core.relevance_scorer import RelevanceScorer
    from src.ingest.job_details_extractor import JobDetailsExtractor
    from src.ingest.resume_parser import PDFResumeParser

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    user_cfg = cfg.get("user", {})
    resume_path = pathlib.Path(user_cfg.get("resume_path", "data/resume.pdf"))

    if not resume_path.exists():
        # Try sample
        resume_path = pathlib.Path("data/sample_resume.pdf")
        if not resume_path.exists():
            click.echo(Fore.RED + "Resume not found in config or default data/resume.pdf")
            sys.exit(1)

    try:
        click.echo(Fore.CYAN + f"Parsing resume: {resume_path}")
        resume_parser = PDFResumeParser()
        resume_text = resume_parser.extract_text(resume_path)

        ai_cfg = cfg.get("ai", {})
        llm = get_llm_client(ai_cfg)
        scorer = RelevanceScorer(llm)
        extractor = JobDetailsExtractor(None)  # No browser needed

        jobs_to_score = []
        if job_id:
            job = extractor.get_cached_job(job_id)
            if not job:
                click.echo(Fore.RED + f"Job {job_id} not found in cache.")
                sys.exit(1)
            jobs_to_score.append(job)
        elif score_all:
            # Find all regular json files (not score/analysis ones)
            # This is tricky because we need to differentiate.
            # Convention: {id}.json is job, {id}_analysis.json is analysis.
            for f in extractor.cache_dir.glob("*.json"):
                if "_" not in f.stem and f.stem.isdigit():
                    job = extractor.get_cached_job(f.stem)
                    if job:
                        jobs_to_score.append(job)
        else:
            click.echo(Fore.YELLOW + "Please provide a JOB_ID or use --all")
            return

        click.echo(Fore.CYAN + f"Scoring {len(jobs_to_score)} jobs...")

        for job in jobs_to_score:
            result = scorer.score_job(resume_text, job)
            if result:
                output_path = extractor.cache_dir / f"{job.id}_analysis.json"
                with open(output_path, "w") as f:
                    json.dump(asdict(result), f, indent=2)

                color = Fore.GREEN if result.score >= 70 else Fore.YELLOW if result.score >= 40 else Fore.RED
                click.echo(f"Job {job.id}: {color}Score {result.score}{Fore.RESET} - {result.reasoning}")
            else:
                click.echo(Fore.RED + f"Failed to score job {job.id}")

    except Exception as e:
        click.echo(Fore.RED + f"Scoring failed: {e}")
        sys.exit(1)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--min-score", default=0, help="Minimum score of jobs to include in analysis")
def analyze_gaps(config: str, min_score: int):
    """
    Analyze missing skills from scored jobs to generate an improvement plan.
    """
    import json

    from src.core.ai import get_llm_client
    from src.core.gap_analysis import GapAnalyzer
    from src.core.relevance_scorer import ScoringResult

    cfg_path = pathlib.Path(config)
    if not cfg_path.exists():
        click.echo(Fore.RED + f"Config file not found: {cfg_path}")
        sys.exit(1)

    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    try:
        ai_cfg = cfg.get("ai", {})
        llm = get_llm_client(ai_cfg)
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
            click.echo(Fore.YELLOW + f"No scored jobs found (with min_score >= {min_score}). Run 'score' first.")
            return

        click.echo(Fore.CYAN + f"Analyzing gaps across {len(results)} jobs...")
        gap_result = analyzer.analyze_gaps(results)

        if gap_result:
            click.echo(Fore.GREEN + "\n=== Top Missing Skills ===")
            for skill, count in gap_result.skill_frequency.items():
                click.echo(f"- {skill}: {count} jobs")

            click.echo(Fore.CYAN + "\n=== Improvement Plan ===")
            click.echo(gap_result.improvement_plan)
        else:
            click.echo(Fore.YELLOW + "Analysis returned no results.")

    except Exception as e:
        click.echo(Fore.RED + f"Gap analysis failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    cli()
