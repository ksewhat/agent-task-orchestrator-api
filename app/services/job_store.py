import uuid
from datetime import datetime, timezone

from app.db.base import SessionLocal
from app.db.models import JobModel
from app.schemas.agent import AgentPlanResponse
from app.schemas.job import JobResponse, JobStatus


def _to_response(row: JobModel) -> JobResponse:
    """ORM 행(row)을 Pydantic 응답 모델로 변환한다."""
    # DB에 JSON으로 저장된 result를 AgentPlanResponse Pydantic 모델로 복원
    result = AgentPlanResponse(**row.result) if row.result else None
    return JobResponse(
        job_id=row.job_id,
        # DB에 문자열로 저장된 status를 Enum으로 변환
        status=JobStatus(row.status),
        user_request=row.user_request,
        context=row.context,
        created_at=row.created_at,
        updated_at=row.updated_at,
        result=result,
        error=row.error,
    )


def create_job(user_request: str, context: str | None = None) -> JobResponse:
    now = datetime.now(timezone.utc)
    job_id = str(uuid.uuid4())

    # with SessionLocal() as session: → 블록을 벗어나면 session.close()가 자동 호출됨
    with SessionLocal() as session:
        row = JobModel(
            job_id=job_id,
            status=JobStatus.PENDING.value,  # Enum → 문자열 "pending"
            user_request=user_request,
            context=context,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)  # commit 후 DB에서 최신값을 다시 읽어옴
        return _to_response(row)


def get_job(job_id: str) -> JobResponse | None:
    with SessionLocal() as session:
        # session.get(Model, pk): 기본키로 단건 조회
        row = session.get(JobModel, job_id)
        if row is None:
            return None
        return _to_response(row)


def update_job_status(
    job_id: str,
    status: JobStatus,
    result: AgentPlanResponse | None = None,
    error: str | None = None,
) -> JobResponse | None:
    with SessionLocal() as session:
        row = session.get(JobModel, job_id)
        if row is None:
            return None

        row.status = status.value
        # Pydantic 모델 → dict로 변환해 JSON 컬럼에 저장
        row.result = result.model_dump() if result is not None else None
        row.error = error
        row.updated_at = datetime.now(timezone.utc)

        session.commit()
        session.refresh(row)
        return _to_response(row)
