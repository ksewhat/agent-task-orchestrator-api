from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.job import JobCreateRequest, JobResponse, JobResultResponse
from app.services import job_store
from app.services.agent_runner import run_agent_plan_job

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=202)
def create_agent_job(request: JobCreateRequest, background_tasks: BackgroundTasks):
    """
    Agent 계획 생성 Job을 등록하고 즉시 job_id를 반환한다.

    - 응답을 기다리지 않고 202 Accepted를 즉시 반환한다.
    - LLM 실행은 백그라운드에서 자동으로 시작된다.
    - 결과는 GET /agent/jobs/{job_id}/result 로 조회한다.
    """
    if not request.user_request.strip():
        raise HTTPException(status_code=400, detail="user_request는 비어 있을 수 없습니다.")

    job = job_store.create_job(request.user_request, request.context)
    background_tasks.add_task(run_agent_plan_job, job.job_id)
    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_agent_job(job_id: str):
    """
    Job의 전체 정보와 현재 상태를 조회한다.

    - status: pending → running → succeeded / failed
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job을 찾을 수 없습니다: {job_id}")
    return job


@router.get("/{job_id}/result", response_model=JobResultResponse)
def get_agent_job_result(job_id: str):
    """
    Job의 실행 결과를 조회한다.

    - succeeded: result 필드에 Agent 계획 데이터가 담겨 있다.
    - failed: error 필드에 실패 원인이 담겨 있다.
    - pending / running: result와 error 모두 null이다.
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job을 찾을 수 없습니다: {job_id}")

    return JobResultResponse(
        job_id=job.job_id,
        status=job.status,
        result=job.result,
        error=job.error,
    )
