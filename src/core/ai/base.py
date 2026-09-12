import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient(ABC):
    """Abstract base class for LLM clients to ensure consistent interface."""

    @abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None, max_tokens: Optional[int] = None) -> str:
        """
        Generates a text response from the LLM.

        Args:
            prompt: The user prompt.
            system_instruction: Optional system instruction or context.
            max_tokens: Optional cap on generated output tokens.

        Returns:
            str: The generated text response.
        """
        pass

    def embed(self, text: str) -> List[float]:
        """
        Generates an embedding vector for the given text.

        Returns an empty list if the provider doesn't support embeddings or the call fails,
        so callers can fall back to keyword-only search instead of crashing.
        """
        return []

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
            return {}

        try:
            # Basic cleanup if LLM wraps in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            return json.loads(response_text, strict=False)
        except json.JSONDecodeError:
            # Fallback: Try to find valid JSON structure (object or array)
            candidates = []
            start_obj = response_text.find("{")
            end_obj = response_text.rfind("}")
            if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
                candidates.append((start_obj, end_obj + 1))

            start_arr = response_text.find("[")
            end_arr = response_text.rfind("]")
            if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
                candidates.append((start_arr, end_arr + 1))

            # Prioritize whichever starts earlier (or whichever spans the outer structure)
            candidates.sort(key=lambda span: (span[0], -(span[1] - span[0])))
            for start, end in candidates:
                try:
                    return json.loads(response_text[start:end], strict=False)
                except json.JSONDecodeError:
                    continue

            logger.error("Failed to parse JSON from LLM: No valid JSON structure found.")
            logger.debug(f"Raw response: {response_text}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error parsing LLM response: {e}")
            return {}
