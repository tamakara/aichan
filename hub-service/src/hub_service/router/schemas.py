from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class HubEvent(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: Literal["qq"]
    message_type: Literal["group", "private"]
    raw_event: dict[str, Any]


class ReminderItem(BaseModel):
    user_id: str
    session_id: str
    content: str
    created_at: datetime
    raw_event: dict[str, Any]


class AgentChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_message: str = Field(min_length=1)


class AgentChatResponse(BaseModel):
    reply: str


class SendMessageRequest(BaseModel):
    session_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    ok: bool
    data: dict[str, Any]
