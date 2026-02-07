import pathlib
import sys

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


if __name__ == "__main__":
    cli()
