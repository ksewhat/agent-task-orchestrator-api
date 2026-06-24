import uuid
from collections import deque
from datetime import datetime, timezone

from app.schemas.history import HistoryEntry
from app.schemas.job import JobStatus

# 최대 100건만 유지한다. 초과 시 가장 오래된 항목이 자동으로 제거된다.
# 서버 재시작 시 데이터가 초기화된다.
_store: deque[HistoryEntry] = deque(maxlen=100)


def add_entry(
    user_request: str,
    status: JobStatus,
    goal: str | None = None,
    step_count: int | None = None,
    error: str | None = None,
    job_id: str | None = None,
    created_at: datetime | None = None,
) -> HistoryEntry:
    now = datetime.now(timezone.utc)
    entry = HistoryEntry(
        entry_id=str(uuid.uuid4()),
        job_id=job_id,
        user_request=user_request,
        status=status,
        goal=goal,
        step_count=step_count,
        error=error,
        created_at=created_at or now,
        completed_at=now,
    )
    _store.append(entry)
    return entry


def get_entries(limit: int = 20) -> list[HistoryEntry]:
    """최신순으로 최대 limit건을 반환한다."""
    recent = list(_store)
    recent.reverse()
    return recent[:limit]


def count() -> int:
    return len(_store)
