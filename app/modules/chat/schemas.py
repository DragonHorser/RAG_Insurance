from uuid import UUID

from pydantic import BaseModel, Field
from typing import  Literal, Any

class ChatRequest(BaseModel):
    """基础对话请求"""

    thread_id: UUID
    message: str | None = Field(default=None, min_length=1)
    decision: dict[str, Any] | None = None

