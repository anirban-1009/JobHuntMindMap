import importlib.metadata

import click
from colorama import Fore, init

from src.core.orchestrator import MindMapApp
from src.utils.logger import setup_logging

init(autoreset=True)


def _get_version() -> str:
    """Returns the installed package version, falling back to a dev placeholder."""
    try:
        return importlib.metadata.version("job-hunt-mindmap")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-dev"


@click.group()
@click.version_option(version=_get_version(), prog_name="mindmap")
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
@click.option("--external-only", is_flag=True, default=False, help="Only run on external sites")
def search(config, headless, external_only):
    """Search for jobs based on configuration."""
    MindMapApp(config).search(headless, external_only=external_only)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=True, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs")
@click.option("--force", is_flag=True, default=False, help="Force re-scrape")
@click.option("--min-fast-score", type=int, default=0, help="Minimum initial NLP score (0-100)")
@click.option("--score", is_flag=True, default=False, help="Perform LLM scoring after scraping")
@click.option("--external-only", is_flag=True, default=False, help="Only run on external sites (skip LinkedIn)")
@click.argument("job_id", required=False)
def scrape(config, headless, limit, force, min_fast_score, score, external_only, job_id):
    """Scrape details for found jobs (or a specific job ID)."""
    MindMapApp(config).scrape(headless, limit, force, min_fast_score, score, external_only, job_id)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--headless", is_flag=True, default=False, help="Run in headless mode")
@click.option("--limit", default=None, type=int, help="Limit number of jobs")
@click.option("--score", is_flag=True, default=False, help="Perform LLM re-scoring after refresh")
@click.option(
    "--unknown-only", is_flag=True, default=False, help="Only refresh jobs with Unknown Title or Unknown Company"
)
def refresh(config, headless, limit, score, unknown_only):
    """Re-scrape details for existing jobs in database."""
    MindMapApp(config).refresh_existing_jobs(headless, limit, score, unknown_only)


@cli.command()
@click.option("--config", default="config.yaml")
@click.option("--all", "score_all", is_flag=True)
@click.argument("job_id", required=False)
def score(config, score_all, job_id):
    """Score jobs against resume."""
    MindMapApp(config).score_jobs(score_all, job_id)


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--min-score", default=0, type=int, help="Minimum score to include")
@click.option("--tag", default=None, help="Specific tag/specialization to analyze (e.g. AI_ML)")
def analyze_gaps(config, min_score, tag):
    """Analyze skill gaps and generate report."""
    MindMapApp(config).analyze_gaps(min_score, tag)


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
@click.option("--max-chars", default=200, type=int, help="Maximum characters for the message")
def refer(config, job_id, name, max_chars):
    """Generate referral request for a job."""
    app = MindMapApp(config)
    res = app.referral(job_id, name, max_chars=max_chars)

    if res is None:
        name = click.prompt(Fore.CYAN + "Enter connection name manually", default="Hiring Manager")
        res = app.referral(job_id, name, max_chars=max_chars)

    if res:
        click.echo(Fore.WHITE + "\n" + "=" * 50)
        click.echo(Fore.GREEN + f"To: {res['to']} {Fore.CYAN}({len(res['message'])}/{max_chars} chars)")
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


@cli.command()
@click.option("--config", default="config.yaml")
def sync_back(config):
    """Sync changes from Obsidian back to the database."""
    MindMapApp(config).sync_back()


@cli.command()
@click.option("--config", default="config.yaml")
def prune(config):
    """Delete Obsidian pages not present in the database."""
    MindMapApp(config).prune()


@cli.command()
@click.option("--config", default="config.yaml")
@click.argument("query")
@click.option("--semantic", is_flag=True, default=False, help="Use embedding-based semantic search")
@click.option("--limit", default=10, type=int, help="Maximum number of results")
@click.option("--reindex", is_flag=True, default=False, help="Reindex changed vault files before searching")
def find(config, query, semantic, limit, reindex):
    """Search the Obsidian vault (keyword by default, --semantic for embeddings)."""
    results = MindMapApp(config).find(query, semantic=semantic, limit=limit, reindex=reindex)

    if not results:
        click.echo(Fore.YELLOW + "No results found.")
        return

    for r in results:
        click.echo(Fore.WHITE + "-" * 50)
        click.echo(Fore.GREEN + f"{r.get('title') or r.get('path')} " + Fore.CYAN + f"[{r.get('category')}]")
        click.echo(Fore.WHITE + r.get("path", ""))
        if "snippet" in r:
            click.echo(r["snippet"])
        elif "distance" in r:
            click.echo(Fore.CYAN + f"distance: {r['distance']:.4f}")
    click.echo(Fore.WHITE + "-" * 50)


@cli.command("evaluate-companies")
@click.option("--config", default="config.yaml", help="Path to config file")
def evaluate_companies_cmd(config):
    """Evaluate and cluster all companies across jobs and network."""
    app = MindMapApp(config)
    evals = app.evaluate_companies()
    click.echo(Fore.GREEN + f"\nSuccessfully evaluated and clustered {len(evals)} companies.")


@cli.command()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--cluster", default=None, help="Filter by action cluster (warm, direct, nurture, watchlist, or all)")
@click.option("--domain", default=None, help="Filter by domain cluster (e.g. GenAI, Enterprise)")
@click.option("--min-score", default=0, type=int, help="Minimum company score (0-100)")
@click.option("--limit", default=25, type=int, help="Maximum number of companies to display")
@click.option(
    "--sort", "sort_by", default="score", type=click.Choice(["score", "jobs", "network", "name"]), help="Sort criteria"
)
def companies(config, cluster, domain, min_score, limit, sort_by):
    """List scored and clustered companies for targeted applications and outreach."""
    app = MindMapApp(config)
    company_list = app.list_companies(cluster=cluster, min_score=min_score, limit=limit, sort_by=sort_by)

    if not company_list:
        click.echo(Fore.YELLOW + "No matching companies found.")
        return

    click.echo(Fore.WHITE + "\n" + "=" * 96)
    click.echo(
        Fore.WHITE + f"{'SCORE':<7}{'COMPANY':<28}{'ACTION CLUSTER':<18}{'JOBS (HI)':<12}{'CONNS (KEY)':<14}{'DOMAIN'}"
    )
    click.echo(Fore.WHITE + "-" * 96)

    for c in company_list:
        score_val = c.get("score", 0)
        if score_val >= 75:
            score_color = Fore.GREEN
        elif score_val >= 55:
            score_color = Fore.CYAN
        else:
            score_color = Fore.YELLOW

        cluster_name = c.get("action_cluster", "Watchlist")
        if "Warm" in cluster_name:
            cluster_color = Fore.GREEN
        elif "Direct" in cluster_name:
            cluster_color = Fore.CYAN
        elif "Nurture" in cluster_name:
            cluster_color = Fore.YELLOW
        else:
            cluster_color = Fore.WHITE

        name = c.get("name", "Unknown")[:26]
        jobs_str = f"{c.get('job_count', 0)} ({c.get('high_match_job_count', 0)})"
        conns_str = f"{c.get('connection_count', 0)} ({c.get('key_connection_count', 0)})"
        domain_name = c.get("domain_cluster", "General")[:22]

        click.echo(
            f"{score_color}{score_val:<7}{Fore.WHITE}{name:<28}{cluster_color}{cluster_name:<18}{Fore.WHITE}{jobs_str:<12}{Fore.CYAN}{conns_str:<14}{Fore.MAGENTA}{domain_name}"
        )

    click.echo(Fore.WHITE + "=" * 96 + "\n")
    click.echo(
        Fore.CYAN + "Tip: Run 'uv run mindmap company <COMPANY_NAME>' for full jobs, connections, and outreach plan."
    )


@cli.command()
@click.argument("company_name")
@click.option("--config", default="config.yaml", help="Path to config file")
def company(company_name, config):
    """Deep-dive into a specific company's opportunities, network, and outreach plan."""
    app = MindMapApp(config)
    dossier = app.get_company_details(company_name)
    if not dossier:
        click.echo(Fore.RED + f"Company '{company_name}' not found.")
        return

    c = dossier["company"]
    jobs = dossier["jobs"]
    conns = dossier["connections"]

    score_val = c.get("score", 0)
    score_color = Fore.GREEN if score_val >= 75 else Fore.CYAN if score_val >= 55 else Fore.YELLOW

    click.echo(Fore.WHITE + "\n" + "=" * 80)
    click.echo(Fore.WHITE + f"COMPANY: {Fore.GREEN}{c.get('name')}  {score_color}[Score: {score_val}/100]")
    click.echo(
        Fore.WHITE
        + f"Cluster: {Fore.CYAN}{c.get('action_cluster')}  |  Domain: {Fore.MAGENTA}{c.get('domain_cluster')}  |  Tier: {Fore.YELLOW}{c.get('target_tier')}"
    )
    click.echo(Fore.WHITE + "-" * 80)

    # Breakdown
    eval_data = c.get("evaluation_data") or {}
    if eval_data:
        click.echo(Fore.WHITE + "Score Breakdown:")
        click.echo(
            f"  - Job Quality & Fit (45%): {Fore.CYAN}{eval_data.get('job_fit_score', 0)}/100  "
            f"{Fore.WHITE}|  Company Domain Fit (35%): {Fore.CYAN}{eval_data.get('company_fit_score', 0)}/100  "
            f"{Fore.WHITE}|  Network Leverage (20%): {Fore.CYAN}{eval_data.get('network_score', 0)}/100"
        )

    # Action Directive
    recommended_action = c.get("recommended_action") or eval_data.get("recommended_action")
    if recommended_action:
        click.echo(Fore.WHITE + f"\nRecommended Action: {Fore.GREEN}{recommended_action}")

    # Open Jobs
    click.echo(Fore.WHITE + f"\nOpen Jobs ({len(jobs)} total):")
    if jobs:
        for j in jobs[:8]:
            j_score = j.get("relevance_score")
            j_color = Fore.GREEN if (j_score or 0) >= 80 else Fore.CYAN if (j_score or 0) >= 70 else Fore.WHITE
            score_txt = f"[{j_score}]" if j_score is not None else "[Unscored]"
            click.echo(f"  - {j_color}{score_txt:<11} {Fore.WHITE}{j.get('title')} ({j.get('location', 'Remote')})")
            if j.get("link"):
                click.echo(f"    Apply: {Fore.CYAN}{j.get('link')}")
    else:
        click.echo(Fore.YELLOW + "  No active jobs in cache for this company.")

    # Connections
    click.echo(Fore.WHITE + f"\nNetwork Contacts ({len(conns)} verified):")
    if conns:
        for p in conns:
            role_type = p.get("role_type", "other")
            role_tag = f"[{role_type.upper()}]" if role_type != "other" else ""
            click.echo(
                f"  - {Fore.GREEN}{p['name']} {Fore.YELLOW}{role_tag} {Fore.WHITE}- {p['title']} (Connected: {p.get('connected_on', 'N/A')})"
            )
    else:
        click.echo(Fore.YELLOW + "  No direct connections found at this company.")

    click.echo(Fore.WHITE + "=" * 80 + "\n")


if __name__ == "__main__":
    cli()
