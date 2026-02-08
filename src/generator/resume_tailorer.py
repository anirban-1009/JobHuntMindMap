import subprocess
from pathlib import Path
from typing import Any, Dict

import jinja2

from src.core.ai import get_llm_client
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ResumeTailorer:
    """Tails a resume for a specific job description using LLM."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the tailorer with configuration.

        Args:
            config (Dict[str, Any]): Project configuration.
        """
        self.config = config
        self.llm = get_llm_client(config.get("ai", config))

        # Setup Jinja2 environment for LaTeX
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = jinja2.Environment(
            block_start_string="{%",
            block_end_string="%}",
            variable_start_string="{{",
            variable_end_string="}}",
            comment_start_string="{#",
            comment_end_string="#}",
            loader=jinja2.FileSystemLoader(str(template_dir)),
        )

    def tailor_resume(self, resume_data: Dict[str, Any], job_description: str) -> Dict[str, Any]:
        """
        Uses LLM to rewrite resume components based on job description.

        Args:
            resume_data (Dict[str, Any]): Original resume data.
            job_description (str): Target job description.

        Returns:
            Dict[str, Any]: Tailored resume data.
        """
        logger.info("Tailoring resume using LLM...")

        # Simplified for now: We ask the LLM to rewrite the summary and bullet points
        # In a real implementation, we would send the full structured data or raw text.

        prompt = self._build_tailoring_prompt(resume_data, job_description)
        response = self.llm.generate(prompt)

        # Parse the LLM response. We expect JSON for structured updates.
        # This is a placeholder for actual parsing logic.
        try:
            import json

            # Extract JSON from potential markdown tags
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()

            tailored_updates = json.loads(response)

            # Merge updates into resume_data
            tailored_data = resume_data.copy()
            tailored_data.update(tailored_updates)
            return tailored_data

        except Exception as e:
            logger.error(f"Failed to parse LLM response for tailoring: {e}")
            logger.debug(f"Raw response: {response}")
            return resume_data  # Fallback to original

    def generate_latex(self, tailored_data: Dict[str, Any], template_name: str = "resume_master.tex.j2") -> str:
        """
        Renders the tailored data into a LaTeX string.

        Args:
            tailored_data (Dict[str, Any]): Data to render.
            template_name (str): Template filename.

        Returns:
            str: Rendered LaTeX content.
        """
        sanitized_data = self._deep_sanitize(tailored_data)
        template = self.jinja_env.get_template(template_name)
        return template.render(**sanitized_data)

    def _deep_sanitize(self, data: Any) -> Any:
        """Recursively sanitize data for LaTeX."""
        if isinstance(data, str):
            return self._sanitize_latex(data)
        elif isinstance(data, list):
            return [self._deep_sanitize(item) for item in data]
        elif isinstance(data, dict):
            return {k: self._deep_sanitize(v) for k, v in data.items()}
        return data

    def compile_pdf(self, latex_content: str, output_path: Path) -> Path:
        """
        Compiles LaTeX content to PDF using pdflatex.

        Args:
            latex_content (str): LaTeX string.
            output_path (Path): Target PDF path.

        Returns:
            Path: Path to the generated PDF.
        """
        # Create a temporary directory for compilation
        temp_dir = output_path.parent / "temp_compile"
        temp_dir.mkdir(parents=True, exist_ok=True)

        tex_file = temp_dir / "resume.tex"
        tex_file.write_text(latex_content, encoding="utf-8")

        try:
            logger.info(f"Compiling PDF to {output_path}...")
            # Run pdflatex twice for references/cross-links if needed
            for _ in range(2):
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(temp_dir), str(tex_file)],
                    capture_output=True,
                    text=True,
                    check=True,
                )

            # Move result to final destination
            pdf_result = temp_dir / "resume.pdf"
            if pdf_result.exists():
                if output_path.exists():
                    output_path.unlink()
                pdf_result.rename(output_path)
                return output_path
            else:
                raise FileNotFoundError("pdflatex failed to produce a PDF.")

        except subprocess.CalledProcessError as e:
            logger.error(f"pdflatex compilation failed: {e.stderr}")
            raise RuntimeError(f"Failed to compile LaTeX: {e.stderr}")
        finally:
            # Cleanup temp files (optional, keeping for debug for now or delete later)
            # In a production app, we should clean up.
            pass

    def _build_tailoring_prompt(self, resume_data: Dict[str, Any], job_description: str) -> str:
        """Prepares the prompt for the LLM."""
        return f"""
        You are an expert career coach and resume writer.
        I will provide you with a structured resume data and a job description.
        Your task is to rewrite the 'professional_summary' and the 'bullets' in the 'experience' section to better align with the job description.
        Focus on matching keywords, highlighting relevant achievements, and removing irrelevant details.
        
        Return ONLY a JSON object with the following keys:
        - "professional_summary": (string) The rewritten summary.
        - "experience": (list of dicts) Each dict must have 'title', 'company', and 'bullets' (list of strings).
        
        RESUME DATA:
        {resume_data}
        
        JOB DESCRIPTION:
        {job_description}
        """

    def _sanitize_latex(self, text: str) -> str:
        """Escapes LaTeX special characters."""
        chars = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\^{}",
            "\\": r"\textbackslash{}",
        }
        return "".join(chars.get(c, c) for c in text)
