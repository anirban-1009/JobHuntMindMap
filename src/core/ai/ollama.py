from typing import Optional

import requests

from src.core.ai.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class OllamaClient(LLMClient):
    """Client for local Ollama instance."""

    def __init__(self, model_name: str = "llama3.2:latest", base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama client.

        Args:
            model_name: Name of the model pulled in Ollama (default: llama3.2:latest).
            base_url: Ollama API base URL (default: http://localhost:11434).
        """
        self.model_name = model_name
        self.base_url = base_url

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generates content using Ollama REST API.

        Args:
            prompt: User prompt for generation.
            system_instruction: Optional system instruction.

        Returns:
            str: Generated text content from Ollama.
        """
        try:
            payload = {"model": self.model_name, "prompt": prompt, "stream": False}
            if system_instruction:
                payload["system"] = system_instruction

            response = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return ""
