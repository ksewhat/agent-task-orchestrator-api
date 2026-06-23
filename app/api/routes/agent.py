from fastapi import APIRouter, HTTPException

from app.schemas.agent import AgentPlanRequest, AgentPlanResponse
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

    try:
        return generate_agent_plan(request.user_request, request.context)
    except LLMClientNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except LLMResponseParseError as e:
        raise HTTPException(status_code=502, detail=str(e))
