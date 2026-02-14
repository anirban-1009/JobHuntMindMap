import click
from colorama import Fore, init

from src.core.orchestrator import MindMapApp
from src.utils.logger import setup_logging

init(autoreset=True)


@click.group()
def cli():
    """Job Hunt Mindmap CLI"""
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def check(config):
    """Validate configuration and environment."""
    MindMapApp(config).check_env()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def login(config):
    """Obtain LinkedIn session cookies manually."""
    MindMapApp(config).login()


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
def search(config, headless):
    """Search for jobs based on configuration."""
    MindMapApp(config).search(headless)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs")
@click.option("--force", is_flag=True, default=False, help="Force re-scrape")
@click.option("--min-fast-score", type=int, default=0, help="Minimum initial NLP score (0-100)")
@click.option("--score", is_flag=True, default=False, help="Perform LLM scoring after scraping")
def scrape(config, headless, limit, force, min_fast_score, score):
    """Scrape details for found jobs."""
    MindMapApp(config).scrape(headless, limit, force, min_fast_score, score)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs")
@click.option("--score", is_flag=True, default=False, help="Perform LLM re-scoring after refresh")
def refresh(config, headless, limit, score):
    """Re-scrape details for existing jobs in database."""
    MindMapApp(config).refresh_existing_jobs(headless, limit, score)


@cli.command()
@click.option("--config", default="config.yaml")
@click.option("--all", "score_all", is_flag=True)
@click.argument("job_id", required=False)
def score(config, score_all, job_id):
    """Score jobs against resume."""
    MindMapApp(config).score_jobs(score_all, job_id)


@cli.command()
@click.option("--config", default="config.yaml")
@click.option("--min-score", default=0)
def analyze_gaps(config, min_score):
    """Analyze skill gaps."""
    MindMapApp(config).analyze_gaps(min_score)


@cli.command()
@click.option("--config", default="config.yaml")
@click.option("--min-score", default=70)
def notify(config, min_score):
    """Send job digest email."""
    MindMapApp(config).notify(min_score)


@cli.command()
@click.option("--config", default="config.yaml")
@click.argument("job_id")
@click.option("--name", default=None)
def refer(config, job_id, name):
    """Generate referral request for a job."""
    app = MindMapApp(config)
    res = app.referral(job_id, name)

    if res is None:
        name = click.prompt(Fore.CYAN + "Enter connection name manually", default="Hiring Manager")
        res = app.referral(job_id, name)

    if res:
        click.echo(Fore.WHITE + "\n" + "=" * 50)
        click.echo(Fore.GREEN + f"To: {res['to']}")
        click.echo(Fore.WHITE + "-" * 50)
        click.echo(res["message"])
        click.echo(Fore.WHITE + "=" * 50 + "\n")


@cli.command()
@click.option("--config", default="config.yaml")
@click.argument("job_id")
def tailor(config, job_id):
    """Generate a tailored resume."""
    app = MindMapApp(config)
    path = app.tailor_resume(job_id)
    if path:
        click.echo(Fore.GREEN + f"Tailored resume saved to: {path}")


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--prompt", default="Say 'Mindmap AI Online'", help="Test prompt")
def test_ai(config, prompt):
    """Test AI provider connection."""
    MindMapApp(config).test_ai(prompt)


@cli.command()
@click.argument("job_id")
@click.option("--config", default="config.yaml", help="Path to config file")
def network(job_id, config):
    """Find connections for a job."""
    MindMapApp(config).find_network(job_id)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
def network_all(config):
    """Find connections for all jobs."""
    MindMapApp(config).map_all_networks()


@cli.command()
@click.option("--config", default="config.yaml")
def sync(config):
    """Sync data to Obsidian."""
    MindMapApp(config).sync()


if __name__ == "__main__":
    cli()
