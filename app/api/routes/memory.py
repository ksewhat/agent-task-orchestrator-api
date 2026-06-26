from fastapi import APIRouter, Query

from app.schemas.memory import MemoryListResponse
from app.services import memory_store

router = APIRouter()


@router.get("", response_model=MemoryListResponse)
def get_agent_memory(limit: int = Query(default=20, ge=1, le=50)):
    """
    Agent의 최근 작업 흐름을 최신 순으로 반환한다.

    - 최신 이벤트가 먼저 (index 0 = 가장 최근)
    - Redis가 꺼져 있으면 빈 목록을 반환한다.
    - limit: 최대 조회 개수 (1~50)
    """
    events = memory_store.get_recent(limit)
    return MemoryListResponse(events=events, count=len(events))
