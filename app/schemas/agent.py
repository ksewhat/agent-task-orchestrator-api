from pydantic import BaseModel, Field


class AgentPlanRequest(BaseModel):
    user_request: str = Field(
        ...,
        description="AI Agent에게 전달할 자연어 요청",
        examples=["FastAPI 기반 웹 서비스를 AWS EC2에 배포하는 계획을 세워줘"],
    )
    context: str | None = Field(
        default=None,
        description="요청에 대한 추가 컨텍스트 (선택)",
        examples=["Python 3.11, PostgreSQL 사용, 팀원 3명"],
    )


class AgentPlanStep(BaseModel):
    order: int = Field(..., description="실행 순서 (1부터 시작)", examples=[1])
    title: str = Field(..., description="단계 제목", examples=["환경 설정"])
    description: str = Field(
        ...,
        description="단계 상세 설명",
        examples=["Python 가상환경을 생성하고 의존성 패키지를 설치한다."],
    )
    expected_output: str = Field(
        ...,
        description="이 단계가 완료되었을 때 기대되는 결과물",
        examples=[".venv 디렉터리, requirements.txt"],
    )


class AgentPlanResponse(BaseModel):
    goal: str = Field(..., description="사용자 요청의 최종 목표")
    summary: str = Field(..., description="전체 실행 계획 요약")
    steps: list[AgentPlanStep] = Field(..., description="순서대로 실행할 단계 목록")
    risks: list[str] = Field(..., description="실행 시 주의해야 할 리스크 목록")
    next_action: str = Field(..., description="지금 당장 실행할 첫 번째 행동")
