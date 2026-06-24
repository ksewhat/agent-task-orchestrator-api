import uuid
from datetime import datetime, timezone

from app.schemas.job import JobResponse, JobStatus

# 인메모리 저장소. 서버 재시작 시 모든 Job 데이터가 초기화된다.
# 다음 단계에서 DB나 Redis로 교체할 수 있도록 함수 인터페이스로 분리해뒀다.
_store: dict[str, JobResponse] = {}


def create_job(user_request: str, context: str | None = None) -> JobResponse:
    now = datetime.now(timezone.utc)
    job = JobResponse(
        job_id=str(uuid.uuid4()),
        status=JobStatus.PENDING,
        user_request=user_request,
        context=context,
        created_at=now,
        updated_at=now,
    )
    _store[job.job_id] = job
    return job


def get_job(job_id: str) -> JobResponse | None:
    return _store.get(job_id)


def update_job_status(
    job_id: str,
    status: JobStatus,
    result=None,
    error: str | None = None,
) -> JobResponse | None:
    """Job 상태를 갱신한다. 다음 단계(백그라운드 실행)에서 사용한다."""
    job = _store.get(job_id)
    if job is None:
        return None

    _store[job_id] = job.model_copy(update={
        "status": status,
        "result": result,
        "error": error,
        "updated_at": datetime.now(timezone.utc),
    })
    return _store[job_id]
