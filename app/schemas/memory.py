from typing import Any

from pydantic import BaseModel


class MemoryEvent(BaseModel):
    event_type: str
    job_id: str | None = None
    # dict[str, Any]: 문자열 키와 임의 타입 값을 허용하는 딕셔너리
    payload: dict[str, Any]
    timestamp: str


class MemoryListResponse(BaseModel):
    events: list[MemoryEvent]
    count: int
