import pathlib
import sys

import click
import yaml
from colorama import Fore, init

init(autoreset=True)


@click.group()
def cli():
    """Job Hunt Mindmap CLI"""
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


if __name__ == "__main__":
    cli()
