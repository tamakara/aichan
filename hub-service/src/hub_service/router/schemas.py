from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


class AgentChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    user_message: str = Field(min_length=1)


class AgentChatResponse(BaseModel):
    reply: str
