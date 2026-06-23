from app.core.config import settings


class LLMClientNotConfiguredError(Exception):
    """OPENAI_API_KEY가 설정되지 않았을 때 발생하는 예외."""
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
