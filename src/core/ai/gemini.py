from typing import Optional

from google import genai
from google.genai import types

from src.core.ai.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(LLMClient):
    """Client for Google Gemini API."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        """
        Initialize Gemini client with API key and model.

        Args:
            api_key: Google AI Studio API Key.
            model_name: Gemini model name (default: gemini-2.0-flash).
        """
        self.api_key = api_key
        self.model_name = model_name
        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client: {e}")
            self.client = None

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generates content using Gemini.

        Args:
            prompt: User prompt for generation.
            system_instruction: Optional system message.

        Returns:
            str: Generated text content.
        """
        if not self.client:
            return ""

        try:
            config = None
            if system_instruction:
                config = types.GenerateContentConfig(system_instruction=system_instruction)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ""
