# backend/services/groq_service.py

import json
import logging
from typing import Any

from groq import AsyncGroq

from backend.agent.schemas import AgentResponse, Message, Role, ToolCall
from backend.core.config import get_settings
from backend.services.llm_base import LLMBase
from backend.tools.base import BaseTool

logger   = logging.getLogger(__name__)
settings = get_settings()


class GroqService(LLMBase):
    """
    Groq implementation of LLMBase.

    Flow per request:
      1. Build Groq-format messages from our Message objects
      2. Send to Groq with tool schemas
      3. If Groq returns tool_calls → execute each tool → send results back
      4. Get final text response → return AgentResponse

    Max 2 rounds of tool calls to keep things simple and fast.
    """

    def __init__(self, tools: list[BaseTool]):
        self._client   = AsyncGroq(api_key=settings.groq_api_key)
        self._model    = settings.groq_model
        self._tools    = {tool.name: tool for tool in tools}  # name → tool map
        self._schemas  = [tool.to_groq_schema() for tool in tools]

    async def chat(
        self,
        messages:      list[Message],
        tools:         list[BaseTool],
        system_prompt: str,
    ) -> AgentResponse:

        # Build the message list Groq expects
        groq_messages = self._build_messages(messages, system_prompt)
        all_tool_calls: list[ToolCall] = []

        try:
            # ── Round 1: initial LLM call ──────────────────────────────────
            response = await self._client.chat.completions.create(
                model       = self._model,
                messages    = groq_messages,
                tools       = self._schemas,
                tool_choice = "auto",
                temperature = settings.groq_temperature,
                max_tokens  = settings.groq_max_tokens,
            )

            choice  = response.choices[0]
            message = choice.message

            # ── No tool calls → return directly ───────────────────────────
            if not message.tool_calls:
                return AgentResponse(
                    message    = message.content or "",
                    tool_calls = [],
                )

            # ── Tool calls → execute them ──────────────────────────────────
            groq_messages.append(message)  # append assistant message with tool_calls

            tool_results, tool_calls_made = await self._execute_tool_calls(
                message.tool_calls
            )
            all_tool_calls.extend(tool_calls_made)
            groq_messages.extend(tool_results)

            # ── Round 2: send tool results back to Groq ────────────────────
            response2 = await self._client.chat.completions.create(
                model       = self._model,
                messages    = groq_messages,
                tools       = self._schemas,
                tool_choice = "none",   # no more tool calls in round 2
                temperature = settings.groq_temperature,
                max_tokens  = settings.groq_max_tokens,
            )

            final_message = response2.choices[0].message.content or ""

            return AgentResponse(
                message    = final_message,
                tool_calls = all_tool_calls,
            )

        except Exception as e:
            logger.exception("GroqService.chat failed")
            return AgentResponse(
                message = (
                    "I'm having trouble connecting right now. "
                    "Please try again in a moment."
                ),
                error = str(e),
            )

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_messages(
        self,
        messages:      list[Message],
        system_prompt: str,
    ) -> list[dict]:
        """Convert our Message objects to Groq's dict format."""
        groq_messages = [{"role": "system", "content": system_prompt}]

        for msg in messages:
            if msg.role == Role.tool:
                groq_messages.append({
                    "role":         "tool",
                    "content":      msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.role == Role.assistant:
                groq_messages.append({
                    "role":    "assistant",
                    "content": msg.content,
                })
            elif msg.role == Role.user:
                groq_messages.append({
                    "role":    "user",
                    "content": msg.content,
                })

        return groq_messages

    async def _execute_tool_calls(
        self,
        tool_calls: list[Any],
    ) -> tuple[list[dict], list[ToolCall]]:
        """
        Execute all tool calls Groq requested.
        Returns:
            - groq-format tool result messages to append to conversation
            - our ToolCall objects for logging
        """
        result_messages  = []
        tool_calls_made  = []

        for tc in tool_calls:
            tool_name = tc.function.name
            tool_id   = tc.id

            # Parse arguments
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(f"Could not parse arguments for tool '{tool_name}'")

            # Look up and execute the tool
            tool = self._tools.get(tool_name)
            if not tool:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                logger.warning(f"Groq called unknown tool: {tool_name}")
            else:
                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                result = await tool.execute(**arguments)

            # Log the tool call
            tool_calls_made.append(ToolCall(
                id        = tool_id,
                tool_name = tool_name,
                arguments = arguments,
            ))

            # Append tool result in Groq format
            result_messages.append({
                "role":         "tool",
                "tool_call_id": tool_id,
                "content":      json.dumps(result),
            })

        return result_messages, tool_calls_made
