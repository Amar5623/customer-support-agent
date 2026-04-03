# backend/agent/schemas.py

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Role(str, Enum):
    user      = "user"
    assistant = "assistant"
    tool      = "tool"
    system    = "system"


class Message(BaseModel):
    role:       Role
    content:    str
    tool_call_id: str | None = None   # only for role=tool responses
    name:         str | None = None   # tool name, only for role=tool


class ToolCall(BaseModel):
    id:        str
    tool_name: str
    arguments: dict[str, Any]


class AgentResponse(BaseModel):
    message:       str                  # final text response to show customer
    tool_calls:    list[ToolCall] = []  # what tools were called (for logging)
    was_escalated: bool = False         # did we hit an escalation trigger
    error:         str | None = None    # if something went wrong


class ChatRequest(BaseModel):
    message:    str    = Field(..., min_length=1, max_length=2000)
    session_id: str    = Field(..., description="Unique conversation session ID")
    user_email: str | None = Field(None, description="Customer email if known")
    order_id:   str | None = Field(None, description="Order ID if customer provided one")


class ChatResponse(BaseModel):
    reply:        str
    session_id:   str
    was_escalated: bool = False
    timestamp:    datetime = Field(default_factory=datetime.utcnow)