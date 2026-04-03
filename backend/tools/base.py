# backend/tools/base.py

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Abstract base class for all agent tools.

    Every tool the LLM can call must inherit from this and implement:
      - name        : unique string identifier Groq uses to call it
      - description : what this tool does (LLM reads this to decide when to use it)
      - parameters  : JSON Schema dict describing the tool's inputs
      - execute()   : the actual logic that runs when the tool is called
    """

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict:
        ...

    def to_groq_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def success(self, data: Any) -> dict:
        return {"success": True, "data": data}

    def error(self, message: str) -> dict:
        logger.warning(f"Tool '{self.name}' returned error: {message}")
        return {"success": False, "error": message}