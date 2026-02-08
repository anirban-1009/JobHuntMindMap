import pathlib
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

from src.core.network_graph import Connection
from src.core.relevance_scorer import ScoringResult
from src.ingest.job_details_extractor import JobDetails
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TemplateManager:
    """Manages Jinja2 templates for Obsidian file generation."""

    def __init__(self, templates_dir: Optional[pathlib.Path] = None):
        """
        Initialize the TemplateManager.

        Args:
            templates_dir: Directory containing Jinja2 templates.
        """
        if templates_dir is None:
            # Default to src/generator/templates
            current_dir = pathlib.Path(__file__).parent
            self.templates_dir = current_dir / "templates"
        else:
            self.templates_dir = templates_dir

        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Templates directory not found: {self.templates_dir}")

        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_job(self, job: JobDetails, score: ScoringResult) -> str:
        """
        Renders the Job.md template.

        Args:
            job: JobDetails object.
            score: ScoringResult object.

        Returns:
            Rendered Markdown string.
        """
        template = self.env.get_template("Job.md.j2")
        return template.render(job=job, score=score)

    def render_company(
        self,
        name: str,
        industry: str = "Unknown",
        location: str = "Unknown",
        website: str = "",
        jobs: Optional[List[Dict[str, str]]] = None,
        people: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        Renders the Company.md template.

        Args:
            name: Company name.
            industry: Industry name.
            location: Company location.
            website: Company website URL.
            jobs: List of job dictionaries (title, filename, status).
            people: List of person dictionaries (name, filename, title).

        Returns:
            Rendered Markdown string.
        """
        jobs = jobs or []
        people = people or []
        template = self.env.get_template("Company.md.j2")
        return template.render(
            name=name,
            industry=industry,
            location=location,
            website=website,
            jobs=jobs,
            people=people,
        )

    def render_person(self, person: Connection) -> str:
        """
        Renders the Person.md template.

        Args:
            person: Connection object.

        Returns:
            Rendered Markdown string.
        """
        template = self.env.get_template("Person.md.j2")
        return template.render(person=person)
