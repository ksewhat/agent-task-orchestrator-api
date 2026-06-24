from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.job import JobStatus


class HistoryEntry(BaseModel):
    entry_id: str = Field(..., description="히스토리 항목 고유 ID (UUID)")
    job_id: str | None = Field(default=None, description="연결된 Job ID (비동기 요청인 경우)")
    user_request: str = Field(..., description="사용자의 원본 요청 텍스트")
    status: JobStatus = Field(..., description="최종 처리 상태 (succeeded / failed)")
    goal: str | None = Field(default=None, description="LLM이 도출한 목표 (성공 시)")
    step_count: int | None = Field(default=None, description="생성된 실행 단계 수 (성공 시)")
    error: str | None = Field(default=None, description="실패 원인 (실패 시)")
    created_at: datetime = Field(..., description="요청 접수 시각 (UTC)")
    completed_at: datetime = Field(..., description="처리 완료 시각 (UTC)")


class HistoryListResponse(BaseModel):
    total: int = Field(..., description="현재 저장된 히스토리 항목 수")
    entries: list[HistoryEntry] = Field(..., description="최신순 히스토리 목록")
