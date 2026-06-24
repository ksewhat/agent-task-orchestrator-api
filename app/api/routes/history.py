from fastapi import APIRouter, Query

from app.schemas.history import HistoryListResponse
from app.services import history_store

router = APIRouter()


@router.get("", response_model=HistoryListResponse)
def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="반환할 최대 항목 수 (1~100)"),
):
    """
    Agent 요청 히스토리를 최신순으로 반환한다.

    - 전체 LLM 결과 대신 goal, step_count 등 요약 정보만 포함한다.
    - 서버 재시작 시 데이터가 초기화된다.
    - 최대 100건까지 저장되며 초과 시 오래된 항목부터 제거된다.
    """
    return HistoryListResponse(
        total=history_store.count(),
        entries=history_store.get_entries(limit),
    )
