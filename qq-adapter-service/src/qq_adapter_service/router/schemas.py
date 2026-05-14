from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class SendMessageRequest(BaseModel):
    session_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    ok: bool
    data: dict[str, Any]


class UserInfoResponse(BaseModel):
    ok: bool
    data: dict[str, Any]


class MessageHistoryData(BaseModel):
    session_id: str
    messages: list[dict[str, Any]]
    next_before_message_id: int | None = None


class MessageHistoryResponse(BaseModel):
    ok: bool
    data: MessageHistoryData


class FilteredEventPayload(BaseModel):
    session_id: str
    user_id: str
    content: str
    source: Literal["qq"] = "qq"
    message_type: Literal["group", "private"]
    raw_event: dict[str, Any]


class OutboundAction(BaseModel):
    action: str
    params: dict[str, Any]


class CleanResult(BaseModel):
    accepted: bool
    ignore_reason: str | None = None
    payload: FilteredEventPayload | None = None

