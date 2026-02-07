import pathlib
import sys

import click
import yaml
from colorama import Fore, init

init(autoreset=True)


@click.group()
def cli():
    """Job Hunt Mindmap CLI"""
    from src.utils.logger import setup_logging

    setup_logging()
    pass


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


if __name__ == "__main__":
    cli()
