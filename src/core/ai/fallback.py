from typing import List, Optional

from src.core.ai.base import LLMClient
from src.utils.logger import get_logger

logger = get_logger(__name__)


class FallbackClient(LLMClient):
    """Client that tries multiple providers in order if one fails."""

    def __init__(self, clients: List[LLMClient]):
        """
        Initialize with a list of clients.

        Args:
            clients: Ordered list of LLMClient instances.
        """
        self.clients = clients

    def generate(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Tries each client in order until one succeeds.
        """
        for client in self.clients:
            try:
                response = client.generate(prompt, system_instruction)
                if response:
                    return response
            except Exception as e:
                logger.warning(f"Provider {client.__class__.__name__} failed: {e}")
                continue

        logger.error("All LLM providers failed.")
        return ""
