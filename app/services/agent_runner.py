from app.schemas.job import JobStatus
from app.services import history_store, job_store
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
    완료 후 히스토리에 요약 정보를 기록한다.
    """
    job = job_store.get_job(job_id)
    if job is None:
        return

    job_store.update_job_status(job_id, JobStatus.RUNNING)

    try:
        result = generate_agent_plan(job.user_request, job.context)
        job_store.update_job_status(job_id, JobStatus.SUCCEEDED, result=result)
        history_store.add_entry(
            user_request=job.user_request,
            status=JobStatus.SUCCEEDED,
            goal=result.goal,
            step_count=len(result.steps),
            job_id=job_id,
            created_at=job.created_at,
        )

    except (LLMClientNotConfiguredError, LLMCallError, LLMResponseParseError) as e:
        error_msg = str(e)
        job_store.update_job_status(job_id, JobStatus.FAILED, error=error_msg)
        history_store.add_entry(
            user_request=job.user_request,
            status=JobStatus.FAILED,
            error=error_msg,
            job_id=job_id,
            created_at=job.created_at,
        )

    except Exception as e:
        error_msg = f"예기치 않은 오류가 발생했습니다: {e}"
        job_store.update_job_status(job_id, JobStatus.FAILED, error=error_msg)
        history_store.add_entry(
            user_request=job.user_request,
            status=JobStatus.FAILED,
            error=error_msg,
            job_id=job_id,
            created_at=job.created_at,
        )
