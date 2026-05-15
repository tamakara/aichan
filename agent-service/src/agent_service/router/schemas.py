from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str


class HealthResponse(BaseModel):
    status: str
