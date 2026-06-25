import uuid
from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import HistoryModel
from app.schemas.history import HistoryEntry
from app.schemas.job import JobStatus


def _to_entry(row: HistoryModel) -> HistoryEntry:
    """ORM 행을 Pydantic 응답 모델로 변환한다."""
    return HistoryEntry(
        entry_id=row.entry_id,
        job_id=row.job_id,
        user_request=row.user_request,
        status=JobStatus(row.status),
        goal=row.goal,
        step_count=row.step_count,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


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
    with SessionLocal() as session:
        row = HistoryModel(
            entry_id=str(uuid.uuid4()),
            job_id=job_id,
            user_request=user_request,
            status=status.value,
            goal=goal,
            step_count=step_count,
            error=error,
            created_at=created_at or now,
            completed_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _to_entry(row)


def get_entries(limit: int = 20) -> list[HistoryEntry]:
    """최신순으로 최대 limit건을 반환한다."""
    with SessionLocal() as session:
        # completed_at 내림차순 정렬 후 limit 건만 가져옴
        rows = (
            session.query(HistoryModel)
            .order_by(HistoryModel.completed_at.desc())
            .limit(limit)
            .all()
        )
        return [_to_entry(row) for row in rows]


def count() -> int:
    with SessionLocal() as session:
        return session.query(HistoryModel).count()
