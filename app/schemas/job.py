from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.agent import AgentPlanResponse


class JobStatus(str, Enum):
    PENDING = "pending"      # 접수됨, 아직 실행 전
    RUNNING = "running"      # 실행 중
    SUCCEEDED = "succeeded"  # 성공적으로 완료
    FAILED = "failed"        # 실패


class JobCreateRequest(BaseModel):
    user_request: str = Field(
        ...,
        description="Agent에게 요청할 작업 내용",
        examples=["FastAPI 서버를 AWS EC2에 배포하는 계획을 세워줘"],
    )
    context: str | None = Field(
        default=None,
        description="추가 컨텍스트 (선택)",
        examples=["Python 3.11, PostgreSQL 사용"],
    )


class JobResponse(BaseModel):
    job_id: str = Field(..., description="Job 고유 ID (UUID)")
    status: JobStatus = Field(..., description="Job 현재 상태")
    user_request: str = Field(..., description="요청 내용")
    context: str | None = Field(default=None, description="추가 컨텍스트")
    created_at: datetime = Field(..., description="Job 생성 시각 (UTC)")
    updated_at: datetime = Field(..., description="마지막 상태 변경 시각 (UTC)")
    result: AgentPlanResponse | None = Field(default=None, description="완료된 경우 Agent 계획 결과")
    error: str | None = Field(default=None, description="실패한 경우 에러 메시지")


class JobResultResponse(BaseModel):
    """GET /agent/jobs/{job_id}/result 전용 응답 스키마."""
    job_id: str = Field(..., description="Job 고유 ID")
    status: JobStatus = Field(..., description="현재 상태")
    result: AgentPlanResponse | None = Field(default=None, description="완료된 경우 Agent 계획 결과")
    error: str | None = Field(default=None, description="실패한 경우 에러 메시지")
