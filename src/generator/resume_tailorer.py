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
            loader=jinja2.FileSystemLoader(str(template_dir)),
            comment_start_string="<#",
            comment_end_string="#>",
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
        import json

        logger.info("Tailoring resume using LLM...")

        # Try up to 3 times with progressively stricter prompting
        max_retries = 3
        for attempt in range(max_retries):
            try:
                prompt = self._build_tailoring_prompt(resume_data, job_description)
                response = self.llm.generate(prompt)

                if not response or not response.strip():
                    if attempt < max_retries - 1:
                        logger.warning(f"Empty response from LLM (attempt {attempt + 1}/{max_retries}). Retrying...")
                        continue
                    else:
                        logger.error("Empty response from LLM after all retries")
                        return resume_data

                # Extract JSON from potential markdown tags
                cleaned_response = response
                if "```json" in cleaned_response:
                    cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
                elif "```" in cleaned_response:
                    cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()

                # Try to parse JSON
                tailored_updates = json.loads(cleaned_response)

                # Validate that we got the expected fields
                if "experience" not in tailored_updates:
                    if attempt < max_retries - 1:
                        logger.warning(f"Missing 'experience' field (attempt {attempt + 1}/{max_retries}). Retrying...")
                        continue
                    else:
                        logger.error("Missing 'experience' field after all retries")
                        return resume_data

                # Merge updates into resume_data
                tailored_data = resume_data.copy()
                tailored_data.update(tailored_updates)

                logger.info(
                    f"Successfully tailored resume with {len(tailored_updates.get('experience', []))} experience entries"
                )
                return tailored_data

            except json.JSONDecodeError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                    logger.debug(f"Problematic response: {response[:500]}...")
                    continue
                else:
                    logger.error(f"Failed to parse LLM response after all retries: {e}")
                    logger.debug(f"Raw response: {response[:1000]}...")
                    return resume_data  # Fallback to original

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Error during resume tailoring (attempt {attempt + 1}/{max_retries}): {e}. Retrying..."
                    )
                    continue
                else:
                    logger.error(f"Failed to tailor resume after all retries: {e}")
                    logger.debug(f"Raw response: {response[:1000] if 'response' in locals() else 'N/A'}...")
                    return resume_data  # Fallback to original

        # Should never reach here, but just in case
        return resume_data

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

        # Inject raw versions of URL fields to prevent escaping in \href
        # This is critical for URLs containing underscores, which sanitizer escapes
        if isinstance(sanitized_data, dict):
            url_fields = ["email", "linkedin", "github", "website"]
            for field in url_fields:
                if field in tailored_data:
                    sanitized_data[f"{field}_raw"] = tailored_data[field]

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
        num_experiences = len(resume_data.get("experience", []))
        return f"""You are an expert career coach and resume writer.

CRITICAL RULES - DO NOT VIOLATE:
1. DO NOT make up, invent, or fabricate ANY information
2. DO NOT add new projects, companies, or experiences that don't exist in the resume
3. DO NOT change dates, job titles, or company names
4. DO NOT add technologies or skills that aren't mentioned in the original resume
5. DO NOT remove or combine any job experiences - ALL {num_experiences} jobs MUST be in the output
6. If someone worked at the same company twice, keep BOTH entries separate
7. ONLY rephrase and emphasize existing achievements to match the job description

Your ONLY task is to:
- Reword the professional_summary to highlight relevant skills for this job
- Rephrase existing bullet points to emphasize keywords from the job description
- You may REORDER bullet points within each job to put most relevant ones first
- You may REMOVE individual bullet points that are less relevant
- You MUST include ALL {num_experiences} experience entries from the resume

RESUME DATA:
{resume_data}

JOB DESCRIPTION:
{job_description}

Return ONLY valid JSON with this structure (showing ALL {num_experiences} jobs):
{{
  "professional_summary": "Reworded summary emphasizing relevant skills",
  "experience": [
    {{
      "title": "EXACT same title from resume",
      "company": "EXACT same company from resume",
      "dates": "EXACT same dates from resume",
      "location": "EXACT same location from resume",
      "bullets": ["Rephrased bullet 1", "Rephrased bullet 2"]
    }},
    ... include ALL {num_experiences} jobs here ...
  ]
}}

CRITICAL: Your output MUST have exactly {num_experiences} entries in the "experience" array.
REMEMBER: Only rephrase existing content. Do NOT invent new information.
"""

    def _sanitize_latex(self, text: str) -> str:
        """Escapes LaTeX special characters, but skips already-escaped ones."""
        if not text:
            return text

        result = []
        i = 0
        while i < len(text):
            # If we find a backslash, check if the next char is already being escaped
            if i < len(text) - 1 and text[i] == "\\":
                next_char = text[i + 1]
                # These are valid LaTeX escapes we should preserve
                if next_char in "&%$#_{}":
                    result.append("\\")
                    result.append(next_char)
                    i += 2
                    continue

            # Otherwise, escape special characters
            char = text[i]
            if char == "&":
                result.append(r"\&")
            elif char == "%":
                result.append(r"\%")
            elif char == "$":
                result.append(r"\$")
            elif char == "#":
                result.append(r"\#")
            elif char == "_":
                result.append(r"\_")
            elif char == "{":
                result.append(r"\{")
            elif char == "}":
                result.append(r"\}")
            elif char == "~":
                result.append(r"\textasciitilde{}")
            elif char == "^":
                result.append(r"\^{}")
            else:
                result.append(char)
            i += 1

        return "".join(result)
