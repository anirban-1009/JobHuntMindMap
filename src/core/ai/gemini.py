from typing import Optional

import google.generativeai as genai

from src.core.ai.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiClient(LLMClient):
    """Client for Google Gemini API."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini client with API key and model.

        Args:
            api_key: Google AI Studio API Key.
            model_name: Gemini model name (default: gemini-2.0-flash-exp).
        """
        self.api_key = api_key
        self.model_name = model_name
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name)

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Generates content using Gemini.

        Args:
            prompt: User prompt for generation.
            system_instruction: Optional system message.

        Returns:
            str: Generated text content.
        """
        try:
            if system_instruction:
                # Prepending system instruction for simple version compatibility
                full_prompt = f"System Instruction: {system_instruction}\n\nUser Prompt: {prompt}"
            else:
                full_prompt = prompt

            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return ""
