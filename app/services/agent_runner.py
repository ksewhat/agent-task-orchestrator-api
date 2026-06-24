from app.schemas.job import JobStatus
from app.services import job_store
from app.services.llm_client import (
    LLMCallError,
    LLMClientNotConfiguredError,
    LLMResponseParseError,
    generate_agent_plan,
)


def run_agent_plan_job(job_id: str) -> None:
    """
    FastAPI BackgroundTasks에 의해 호출되는 LLM 실행 함수.

    상태 전환: PENDING → RUNNING → SUCCEEDED / FAILED
    실행 도중 발생하는 모든 예외를 잡아 FAILED 상태와 에러 메시지로 저장한다.
    """
    job = job_store.get_job(job_id)
    if job is None:
        return

    job_store.update_job_status(job_id, JobStatus.RUNNING)

    try:
        result = generate_agent_plan(job.user_request, job.context)
        job_store.update_job_status(job_id, JobStatus.SUCCEEDED, result=result)

    except (LLMClientNotConfiguredError, LLMCallError, LLMResponseParseError) as e:
        job_store.update_job_status(job_id, JobStatus.FAILED, error=str(e))

    except Exception as e:
        job_store.update_job_status(
            job_id,
            JobStatus.FAILED,
            error=f"예기치 않은 오류가 발생했습니다: {e}",
        )
