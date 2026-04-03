# backend/services/llm_base.py

from abc import ABC, abstractmethod
from backend.agent.schemas import AgentResponse, Message
from backend.tools.base import BaseTool


class LLMBase(ABC):
    """
    Abstract interface for any LLM provider.
    Swap Groq for OpenAI by changing one line in container.py.
    """

    @abstractmethod
    async def chat(
        self,
        messages:      list[Message],
        tools:         list[BaseTool],
        system_prompt: str,
    ) -> AgentResponse:
        """
        Send messages to the LLM, execute any tool calls it makes,
        and return the final response.

        Args:
            messages:      Full conversation history
            tools:         Available tools the LLM can call
            system_prompt: Built from knowledge files for this request

        Returns:
            AgentResponse with the final message and metadata
        """
        ...