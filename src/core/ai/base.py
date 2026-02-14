import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM clients to ensure consistent interface."""

    @abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generates a text response from the LLM.

        Args:
            prompt: The user prompt.
            system_instruction: Optional system instruction or context.

        Returns:
            str: The generated text response.
        """
        pass

    def _sanitize_json_response(self, text: str) -> str:
        """
        Sanitize LLM response to handle common JSON issues.

        Args:
            text: Raw LLM response text

        Returns:
            Sanitized text ready for JSON parsing
        """
        # Remove BOM and other invisible characters
        text = text.strip("\ufeff\u200b\u200c\u200d")

        # Replace literal newlines and tabs within JSON strings with escaped versions
        # This regex finds strings and replaces control chars only within them
        def replace_control_chars(match):
            string_content = match.group(0)
            # Replace literal newlines, tabs, carriage returns with escaped versions
            string_content = string_content.replace("\n", "\\n")
            string_content = string_content.replace("\r", "\\r")
            string_content = string_content.replace("\t", "\\t")
            return string_content

        # Apply to content within quotes (basic approach)
        # Note: This is a simple heuristic and may not catch all edge cases
        try:
            # More robust: only process if it looks like JSON
            if "{" in text and "}" in text:
                # Replace control characters in the entire response
                text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
        except Exception as e:
            logger.warning(f"Error during JSON sanitization: {e}")

        return text

    def generate_json(self, prompt: str, system_instruction: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates a JSON response from the LLM.

        Args:
            prompt: The user prompt.
            system_instruction: Optional system instruction.

        Returns:
            Dict[str, Any]: A dictionary parsed from the LLM's JSON output.
        """
        response_text = self.generate(prompt, system_instruction)
        if not response_text:
            logger.warning("Empty response from LLM")
            return {}

        try:
            # Basic cleanup if LLM wraps in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            # Sanitize before parsing
            response_text = self._sanitize_json_response(response_text)

            return json.loads(response_text)
        except json.JSONDecodeError as e:
            # Fallback: Try to find the first '{' and last '}'
            logger.warning(f"Initial JSON parse failed: {e}. Attempting fallback extraction.")
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                try:
                    extracted = response_text[start : end + 1]
                    sanitized = self._sanitize_json_response(extracted)
                    return json.loads(sanitized)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from LLM (fallback): {e}")
                    logger.debug(f"Extracted text: {response_text[start : end + 1][:500]}...")
                    return {}
            else:
                logger.error("Failed to parse JSON from LLM: No JSON object found.")
                logger.debug(f"Raw response: {response_text[:500]}...")
                return {}
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")
            return {}
