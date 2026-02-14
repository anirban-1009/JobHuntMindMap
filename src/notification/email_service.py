import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from src.notification.providers import get_provider
from src.utils.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    """Service to handle sending email notifications."""

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize the email service with configuration.

        Args:
            config: The full project configuration dictionary.
        """
        self.config = config
        self.email_config = config.get("notifications", {}).get("email", {})
        self.user_config = config.get("user", {})

        self.enabled = self.email_config.get("enabled", False)
        self.provider_type = self.email_config.get("provider", "smtp")

        # Resolve all secrets in the email config before passing to provider
        resolved_config = self.email_config.copy()
        for key, value in resolved_config.items():
            if isinstance(value, str):
                resolved_config[key] = self._resolve_secret(value)

        self.provider = get_provider(self.provider_type, resolved_config)

        self.recipient_email = self.user_config.get("email")
        self.user_name = self.user_config.get("full_name", "User")
        self.from_email = resolved_config.get("smtp_user")

        # Setup Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _resolve_secret(self, value: str) -> str:
        """
        Resolves secrets from environment variables if in ${VAR} format.

        Args:
            value: The string to resolve.

        Returns:
            str: The resolved secret or the original value.
        """
        if value and isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var, "")
        return value

    def send_job_digest(self, scored_jobs: List[Dict[str, Any]]) -> bool:
        """
        Generates and sends an HTML email digest of scored jobs with tailored resumes attached.

        Args:
            scored_jobs: List of dictionaries containing 'job' (JobDetails) and 'score' (ScoringResult).

        Returns:
            bool: True if sent successfully (or disabled), False otherwise.
        """
        if not self.enabled:
            logger.info("Email notifications are disabled.")
            return True

        if not scored_jobs:
            logger.info("No jobs to include in the digest.")
            return True

        if not self.recipient_email:
            logger.error("No recipient email found in configuration.")
            return False

        try:
            # Prepare message
            msg = MIMEMultipart("mixed")
            msg["Subject"] = f"Job Digest: {len(scored_jobs)} New Matches Found"
            msg["From"] = self.from_email
            msg["To"] = self.recipient_email

            # Create the email body
            msg_body = MIMEMultipart("alternative")

            # Render HTML
            template = self.jinja_env.get_template("job_digest.html.j2")
            html_content = template.render(user_name=self.user_name, jobs=scored_jobs)

            # Add body parts
            text_fallback = f"Hi {self.user_name},\n\nYou have {len(scored_jobs)} new job matches."
            msg_body.attach(MIMEText(text_fallback, "plain"))
            msg_body.attach(MIMEText(html_content, "html"))

            msg.attach(msg_body)

            # Generate and attach tailored resumes for each job
            logger.info("Generating tailored resumes for email attachments...")
            for item in scored_jobs:
                job = item["job"]
                try:
                    resume_path = self._generate_tailored_resume(job)
                    if resume_path and resume_path.exists():
                        with open(resume_path, "rb") as f:
                            pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                            pdf_attachment.add_header(
                                "Content-Disposition", "attachment", filename=f"Resume_{job.id}.pdf"
                            )
                            msg.attach(pdf_attachment)
                            logger.info(f"Attached resume for job {job.id}")
                except Exception as e:
                    logger.warning(f"Failed to attach resume for job {job.id}: {e}")

            # Send via Provider
            logger.info(f"Sending email digest via {self.provider_type} to {self.recipient_email}...")
            return self.provider.send(msg)

        except Exception as e:
            logger.error(f"Failed to send email digest: {e}")
            return False

    def _generate_tailored_resume(self, job) -> Path:
        """
        Generates a tailored resume for a specific job.

        Args:
            job: JobDetails object

        Returns:
            Path to the generated PDF resume
        """
        try:
            import json

            from src.generator.resume_tailorer import ResumeTailorer

            output_path = Path("output/resumes") / f"Resume_{job.id}.pdf"

            # Check if resume already exists
            if output_path.exists():
                logger.info(f"Using existing tailored resume for job {job.id}")
                return output_path

            # Load resume data
            resume_json_path = Path("data/resume.json")
            if not resume_json_path.exists():
                logger.error(f"Resume data not found at {resume_json_path}")
                return None

            with open(resume_json_path, "r") as f:
                resume_data = json.load(f)

            # Generate new resume
            logger.info(f"Generating tailored resume for job {job.id}")
            tailorer = ResumeTailorer(self.config)

            # Construct job description
            job_desc = f"Title: {job.title}\nCompany: {job.company}\n\n{job.description}"

            # Tailor the resume
            tailored_data = tailorer.tailor_resume(resume_data, job_desc)

            # Generate LaTeX
            latex = tailorer.generate_latex(tailored_data)

            # Compile PDF
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result = tailorer.compile_pdf(latex, output_path)

            return result if result else None

        except Exception as e:
            logger.error(f"Error generating tailored resume for job {job.id}: {e}")
            return None
