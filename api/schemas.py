from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MAX_QUERY_CHARS = 4000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 16000


class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content 不能为空")
        return value


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query 不能为空")
        return value

    @model_validator(mode="after")
    def history_total_must_be_bounded(self):
        if sum(len(message.content) for message in self.history) > MAX_HISTORY_CHARS:
            raise ValueError(f"history 总长度不能超过 {MAX_HISTORY_CHARS} 个字符")
        return self


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]


class RagSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query 不能为空")
        return value


class RagSearchItem(BaseModel):
    rank: int
    source: str
    content: str
    distance: float | None
    metadata: dict[str, Any]


class RagSearchResponse(BaseModel):
    query: str
    top_k: int
    score_type: Literal["distance"] = "distance"
    results: list[RagSearchItem]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["zhisaotong-agent"] = "zhisaotong-agent"
