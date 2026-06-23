import json

from openai import OpenAIError

from app.core.config import settings


class LLMClientNotConfiguredError(Exception):
    """OPENAI_API_KEY가 설정되지 않았을 때 발생하는 예외."""
    pass


class LLMCallError(Exception):
    """OpenAI API 호출 자체가 실패했을 때 발생하는 예외."""
    pass


class LLMResponseParseError(Exception):
    """LLM 응답을 파싱하거나 스키마에 맞추는 데 실패했을 때 발생하는 예외."""
    pass


def get_llm_client():
    """
    OpenAI 클라이언트 인스턴스를 반환한다.

    API Key가 없을 경우 서버 시작 시점이 아니라
    이 함수를 호출하는 시점에 예외를 발생시킨다.
    """
    if not settings.openai_api_key:
        raise LLMClientNotConfiguredError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 OPENAI_API_KEY를 입력해주세요."
        )

    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


def generate_agent_plan(user_request: str, context: str | None = None):
    """
    사용자 요청을 받아 AI Agent 실행 계획을 생성한다.

    LLM에게 JSON 응답을 강제하고, 응답을 AgentPlanResponse로 변환해 반환한다.
    """
    from pydantic import ValidationError
    from app.schemas.agent import AgentPlanResponse

    client = get_llm_client()

    system_prompt = (
        "너는 AI Agent 실행 계획을 설계하는 planner다.\n"
        "사용자의 요청을 실제 작업 가능한 단위로 나누어 JSON 형식으로 반환한다.\n\n"
        "규칙:\n"
        "- 반드시 JSON만 반환하라.\n"
        "- 마크다운 코드블록을 사용하지 말라.\n"
        "- steps는 실행 순서대로 order 1부터 시작하라.\n"
        "- 응답 필드는 goal, summary, steps, risks, next_action만 포함하라.\n\n"
        "JSON 응답 형식:\n"
        "{\n"
        '  "goal": "최종 목표",\n'
        '  "summary": "전체 계획 요약",\n'
        '  "steps": [\n'
        '    {\n'
        '      "order": 1,\n'
        '      "title": "단계 제목",\n'
        '      "description": "단계 설명",\n'
        '      "expected_output": "예상 결과물"\n'
        '    }\n'
        '  ],\n'
        '  "risks": ["리스크 1", "리스크 2"],\n'
        '  "next_action": "바로 실행할 첫 번째 행동"\n'
        "}"
    )

    user_message = f"사용자 요청: {user_request}"
    if context:
        user_message += f"\n\n추가 컨텍스트: {context}"

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
    except OpenAIError as e:
        raise LLMCallError(f"OpenAI API 호출에 실패했습니다: {e}")

    raw_content = response.choices[0].message.content

    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError:
        raise LLMResponseParseError(
            "LLM 응답을 JSON으로 파싱하는 데 실패했습니다. "
            f"원본 응답: {raw_content[:200]}"
        )

    try:
        return AgentPlanResponse(**data)
    except (ValidationError, TypeError) as e:
        raise LLMResponseParseError(
            f"LLM 응답이 예상한 스키마와 맞지 않습니다: {e}"
        )
