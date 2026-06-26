from fastapi import APIRouter, HTTPException

from app.schemas.job import JobCreateRequest, JobResponse, JobResultResponse, JobStatus
from app.services import job_store, memory_store
from app.services.agent_runner import run_agent_plan_job
from app.services.task_queue import task_queue

router = APIRouter()


@router.post("", response_model=JobResponse, status_code=202)
def create_agent_job(request: JobCreateRequest):
    """
    Agent 계획 생성 Job을 RQ 큐에 등록하고 즉시 job_id를 반환한다.

    - 응답을 기다리지 않고 202 Accepted를 즉시 반환한다.
    - LLM 실행은 RQ Worker가 별도 프로세스에서 처리한다.
    - 결과는 GET /agent/jobs/{job_id}/result 로 조회한다.
    """
    if not request.user_request.strip():
        raise HTTPException(status_code=400, detail="user_request는 비어 있을 수 없습니다.")

    job = job_store.create_job(request.user_request, request.context)
    memory_store.push_event(
        memory_store.EVENT_JOB_CREATED,
        payload={"user_request": job.user_request, "context": job.context},
        job_id=job.job_id,
    )

    try:
        # task_queue.enqueue(): 함수와 인수를 Redis 큐에 등록
        # RQ Worker가 실행 중이면 즉시 작업을 가져가 처리한다.
        task_queue.enqueue(run_agent_plan_job, job.job_id)
    except Exception as e:
        job_store.update_job_status(
            job.job_id,
            JobStatus.FAILED,
            error=f"작업 큐 등록에 실패했습니다. Redis가 실행 중인지 확인하세요: {e}",
        )
        raise HTTPException(
            status_code=503,
            detail=f"작업 큐에 연결할 수 없습니다. Redis가 실행 중인지 확인하세요.",
        )

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
