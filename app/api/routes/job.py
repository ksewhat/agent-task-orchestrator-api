from fastapi import APIRouter, HTTPException

from app.schemas.job import JobCreateRequest, JobResponse
from app.services import job_store

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=202)
def create_job(request: JobCreateRequest):
    """
    Agent 작업을 Job으로 등록하고 job_id를 반환한다.

    - 즉시 실행하지 않고 PENDING 상태로 등록만 한다.
    - 반환된 job_id로 GET /jobs/{job_id}에서 상태를 조회할 수 있다.
    - 실제 LLM 실행은 다음 단계에서 백그라운드로 처리한다.
    """
    if not request.user_request.strip():
        raise HTTPException(status_code=400, detail="user_request는 비어 있을 수 없습니다.")

    return job_store.create_job(request.user_request, request.context)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str):
    """
    job_id로 Job 상태를 조회한다.

    - status: pending / running / completed / failed
    - 완료된 경우 result 필드에 Agent 계획 결과가 담긴다. (다음 단계 이후)
    - 실패한 경우 error 필드에 에러 메시지가 담긴다.
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job을 찾을 수 없습니다: {job_id}")

    return job
