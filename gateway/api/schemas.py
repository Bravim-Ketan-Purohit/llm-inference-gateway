"""OpenAI-compatible request/response schemas."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ─── Request schemas ───────────────────────────────────────────────────────────


class FunctionDefinition(BaseModel):
    """Function definition for tool calling."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """Tool definition wrapping a function."""

    type: str = "function"
    function: FunctionDefinition


class ResponseFormat(BaseModel):
    """Response format specification."""

    type: str = "text"  # "text" | "json_object"


class ChatMessage(BaseModel):
    """A single message in the conversation."""

    role: str
    content: str | None = None
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible chat completion request."""

    model: str
    messages: list[ChatMessage]
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    stop: str | list[str] | None = None
    tools: list[ToolDefinition] | None = None
    response_format: ResponseFormat | None = None
    user: str | None = None
    n: int = 1
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0


# ─── Response schemas ──────────────────────────────────────────────────────────


class UsageInfo(BaseModel):
    """Token usage information."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    """Message in a completion choice."""

    role: str = "assistant"
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


class Choice(BaseModel):
    """A single completion choice."""

    index: int = 0
    message: ChoiceMessage
    finish_reason: str | None = "stop"


class ChatCompletionResponse(BaseModel):
    """OpenAI-compatible chat completion response."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[Choice]
    usage: UsageInfo = Field(default_factory=UsageInfo)
    system_fingerprint: str | None = None


# ─── Streaming schemas ─────────────────────────────────────────────────────────


class DeltaMessage(BaseModel):
    """Delta message for streaming."""

    role: str | None = None
    content: str | None = None


class StreamChoice(BaseModel):
    """A streaming choice."""

    index: int = 0
    delta: DeltaMessage
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """A streaming chunk."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[StreamChoice]


# ─── Model listing ─────────────────────────────────────────────────────────────


class ModelInfo(BaseModel):
    """Model metadata."""

    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "llm-gateway"


class ModelListResponse(BaseModel):
    """Response for /v1/models."""

    object: str = "list"
    data: list[ModelInfo] = Field(default_factory=list)
