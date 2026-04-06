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

# Round 2 (after tool results) only needs to generate a short reply.
# Keeping this low reduces TPM usage and avoids hitting rate limits.
_ROUND2_MAX_TOKENS = 600


class GroqService(LLMBase):
    """
    Groq implementation of LLMBase.

    Flow per request:
      1. Build Groq-format messages from our Message objects
      2. Send to Groq with tool schemas (Round 1)
      3. If Groq returns tool_calls → execute each tool → send results back
      4. Get final text response (Round 2) → return AgentResponse

    Two rounds of Groq calls per tool-using turn.
    Round 1: full context + tool schemas
    Round 2: tool results only, no more tool calls, shorter max_tokens
    """

    def __init__(self, tools: list[BaseTool]):
        self._client   = AsyncGroq(api_key=settings.groq_api_key)
        self._model    = settings.groq_model
        self._tools    = {tool.name: tool for tool in tools}
        self._schemas  = [tool.to_groq_schema() for tool in tools]

    async def chat(
        self,
        messages:      list[Message],
        tools:         list[BaseTool],
        system_prompt: str,
    ) -> AgentResponse:

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
            # Strip the text content from Round 1's assistant message before
            # appending. Smaller models generate a narration alongside tool_calls
            # ("I'm going to look that up..."). If that text reaches Round 2,
            # the model treats it as context and keeps narrating. Nulling it out
            # keeps the conversation clean — only the tool_calls array matters here.
            groq_messages.append({
                "role":       "assistant",
                "content":    None,
                "tool_calls": message.tool_calls,
            })

            tool_results, tool_calls_made = await self._execute_tool_calls(
                message.tool_calls
            )
            all_tool_calls.extend(tool_calls_made)
            groq_messages.extend(tool_results)

            # ── Round 2: send tool results back ────────────────────────────
            # Lower temperature on Round 2 — the reply should be factual and
            # grounded in the tool result, not creative. This reduces hallucination.
            response2 = await self._client.chat.completions.create(
                model       = self._model,
                messages    = groq_messages,
                tools       = self._schemas,
                tool_choice = "none",
                temperature = min(settings.groq_temperature, 0.1),
                max_tokens  = _ROUND2_MAX_TOKENS,
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
        result_messages  = []
        tool_calls_made  = []

        for tc in tool_calls:
            tool_name = tc.function.name
            tool_id   = tc.id

            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
                logger.warning(f"Could not parse arguments for tool '{tool_name}'")

            tool = self._tools.get(tool_name)
            if not tool:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}
                logger.warning(f"Groq called unknown tool: {tool_name}")
            else:
                logger.info(f"Executing tool: {tool_name} with args: {arguments}")
                result = await tool.execute(**arguments)

            tool_calls_made.append(ToolCall(
                id        = tool_id,
                tool_name = tool_name,
                arguments = arguments,
            ))

            result_messages.append({
                "role":         "tool",
                "tool_call_id": tool_id,
                "content":      json.dumps(result),
            })

        return result_messages, tool_calls_made