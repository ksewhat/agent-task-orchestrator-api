from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.schemas.agent import AgentPlanRequest, AgentPlanResponse
from app.schemas.job import JobStatus
from app.services import history_store, memory_store
from app.services.memory_store import build_memory_context
from app.services.llm_client import (
    LLMCallError,
    LLMClientNotConfiguredError,
    LLMResponseParseError,
    generate_agent_plan,
)

router = APIRouter()


@router.post("/plan", response_model=AgentPlanResponse)
def create_agent_plan(request: AgentPlanRequest):
    if not request.user_request.strip():
        raise HTTPException(
            status_code=400,
            detail="user_request는 비어 있을 수 없습니다.",
        )

    created_at = datetime.now(timezone.utc)

    try:
        memory_context = build_memory_context()
        result = generate_agent_plan(request.user_request, request.context, memory_context)
        history_store.add_entry(
            user_request=request.user_request,
            status=JobStatus.SUCCEEDED,
            goal=result.goal,
            step_count=len(result.steps),
            created_at=created_at,
        )
        memory_store.push_event(
            memory_store.EVENT_PLAN_GENERATED,
            payload={
                "user_request": request.user_request,
                "goal": result.goal,
                "step_count": len(result.steps),
            },
        )
        return result

    except LLMClientNotConfiguredError as e:
        history_store.add_entry(
            user_request=request.user_request,
            status=JobStatus.FAILED,
            error=str(e),
            created_at=created_at,
        )
        memory_store.push_event(
            memory_store.EVENT_PLAN_FAILED,
            payload={"user_request": request.user_request, "error": str(e)},
        )
        raise HTTPException(status_code=503, detail=str(e))

    except (LLMCallError, LLMResponseParseError) as e:
        history_store.add_entry(
            user_request=request.user_request,
            status=JobStatus.FAILED,
            error=str(e),
            created_at=created_at,
        )
        memory_store.push_event(
            memory_store.EVENT_PLAN_FAILED,
            payload={"user_request": request.user_request, "error": str(e)},
        )
        raise HTTPException(status_code=502, detail=str(e))
