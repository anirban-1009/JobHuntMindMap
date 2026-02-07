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

            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {e}")
            logger.debug(f"Raw response: {response_text}")
            return {}
