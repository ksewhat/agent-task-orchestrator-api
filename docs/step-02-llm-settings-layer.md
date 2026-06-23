# Step 02. LLM API 연동을 위한 설정 계층 추가

> 학습 일자: 2026-06-23
> 목표: OpenAI API 연동을 준비하되, 실제 호출 없이 설정 계층과 클라이언트 초기화 구조만 갖춘다.

---

## 1. 이번 단계에서 추가한 것

| 변경 사항 | 내용 |
|----------|------|
| `app/core/config.py` | `OPENAI_API_KEY` Optional 필드 추가 |
| `app/services/llm_client.py` | LLM 클라이언트 초기화 준비 구조 신규 생성 |
| `.env.example` | `OPENAI_API_KEY` 항목 추가 |
| `requirements.txt` | `openai` 패키지 추가 |
| `README.md` | `.env` 설정 방법 섹션 보강 |

현재 단계에서 실제 OpenAI API를 호출하는 기능은 없다.
다음 단계에서 `get_llm_client()`를 활용해 실제 호출 로직을 붙일 예정이다.

---

## 2. 왜 settings 계층을 분리하는가

처음에는 API Key를 그냥 코드에 직접 쓰면 안 되나 싶었다.
실제로 간단한 스크립트 수준에서는 그렇게 해도 돌아가긴 한다.
하지만 팀 프로젝트나 실제 서비스에서는 몇 가지 이유로 설정값을 분리한다.

**보안**
API Key를 코드에 직접 쓰면 Git 히스토리에 남는다. 한 번 GitHub에 올라간 Key는 이미 노출된 것으로 봐야 하고, 결국 폐기해야 한다. `.env` 파일로 분리하고 `.gitignore`에 추가하면 이 문제를 원천 차단할 수 있다.

**환경 분리**
개발(local), 테스트(staging), 운영(production) 환경마다 다른 API Key, DB 주소 등을 써야 할 때, 코드를 건드리지 않고 `.env` 파일만 바꾸면 된다. 코드는 동일하고 설정만 달라지는 구조가 이상적이다.

**유지보수**
설정값이 코드 여기저기에 흩어져 있으면, 나중에 API Key를 바꿔야 할 때 어디를 고쳐야 하는지 찾기 어렵다. `settings` 객체 한 곳에서 관리하면 변경이 단순해진다.

**테스트 용이성**
테스트 환경에서는 진짜 API Key 대신 가짜 값을 넣거나, `settings`를 목(mock)으로 교체하기 쉽다.

**배포 환경 대응**
클라우드(AWS, GCP, Azure 등)에서는 환경변수를 인프라 수준에서 주입한다. 코드가 환경변수를 읽는 구조로 되어 있으면 배포 환경에서도 별도 수정 없이 바로 동작한다.

---

## 3. 왜 API Key가 없어도 서버가 죽지 않게 설계했는가

처음에는 "API Key가 없으면 어차피 LLM 기능을 못 쓰는데, 서버 시작부터 막으면 안 되나?" 싶었다.

하지만 이 프로젝트에는 `/health` 같이 LLM과 전혀 관계없는 API도 있다. 서버 시작 시점에 API Key를 강제하면, Key가 없는 환경(CI 서버, 새 팀원 로컬 환경 등)에서는 서버 자체가 뜨지 않는 문제가 생긴다.

실제 서비스에서도 기능별로 필요한 자원이 다르다.
전체 서버를 하나의 Key에 묶으면, Key 하나 문제로 전체 서비스가 죽는 상황이 된다.

그래서 이번에는 이런 구조를 택했다.

```python
def get_llm_client():
    if not settings.openai_api_key:
        raise LLMClientNotConfiguredError(
            "OPENAI_API_KEY가 설정되지 않았습니다."
        )
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)
```

서버는 아무 문제 없이 시작하고, LLM 기능을 실제로 쓰려는 순간에 명확한 에러를 던진다.
에러 메시지도 "왜 안 되는지"를 바로 알 수 있게 구체적으로 작성했다.

---

## 4. `.env`와 `.env.example`의 차이

처음에는 두 파일의 차이가 헷갈렸다.

| 파일 | 역할 | Git 커밋 여부 |
|------|------|--------------|
| `.env` | 실제 API Key 등 비밀값을 담는 파일 | 절대 올리면 안 됨 |
| `.env.example` | 어떤 환경변수가 필요한지 알려주는 샘플 | 올려도 됨 (실제 값 없음) |

`.env.example`을 Git에 올려두면, 새 팀원이 프로젝트를 클론했을 때 "어떤 환경변수를 세팅해야 하는지"를 바로 알 수 있다. README에 일일이 적지 않아도 샘플 파일이 그 역할을 한다.

실제로 자주 쓰는 패턴은 이렇다.

```powershell
# 처음 프로젝트 셋업할 때
Copy-Item .env.example .env
notepad .env  # 여기서 실제 API Key 입력
```

---

## 5. `get_llm_client()` 설계 포인트

이번 단계에서 실제 API 호출은 없지만, 다음 단계를 위해 클라이언트 초기화 함수를 미리 만들었다.

```python
from openai import OpenAI
return OpenAI(api_key=settings.openai_api_key)
```

이 부분은 함수 내부에서 `import`를 한다. 파일 상단에서 `import openai`를 하면, `openai` 패키지가 없을 때 서버 시작 자체가 실패할 수 있다. 함수 내부에서 임포트하면 실제 호출 전까지 패키지 존재 여부에 영향받지 않는다.

또 `LLMClientNotConfiguredError`라는 커스텀 예외 클래스를 만들어뒀다. 이렇게 하면 나중에 API 엔드포인트에서 이 예외를 잡아서 HTTP 응답으로 변환할 때 훨씬 깔끔하게 처리할 수 있다.

---

## 6. 다음 단계에서 할 일

이번 단계에서 기반을 만들었으니, 다음 단계에서는 실제 LLM 호출 기능을 붙인다.

예정된 작업:

* `/llm/summarize` 또는 `/tasks/plan` 같은 엔드포인트 추가
* `get_llm_client()`를 활용한 OpenAI API 호출 함수 구현
* 요청(Request) / 응답(Response) 스키마 정의 (Pydantic 모델 사용)
* API Key 누락 시 HTTP 422 또는 503으로 명확한 응답 반환
* 기본 테스트 코드 추가

---

## 이번 단계 핵심 포인트

**설정값은 코드 밖에서 관리한다.**
환경변수는 배포 환경에 따라 달라지고, 비밀값은 코드에 남으면 안 된다. `pydantic-settings`를 쓰면 `.env` 파일을 타입 안전하게 읽을 수 있어서 편하다.

**실패는 가능한 늦게, 메시지는 가능한 명확하게.**
서버 시작 시점에 모든 걸 검증하면 유연성이 떨어진다. 실제 기능이 필요한 시점에 검증하되, 왜 실패했는지는 바로 알 수 있게 해야 한다.

**지금 필요한 것만 만든다.**
아직 LLM API를 호출하지 않는다. 그래도 다음 단계를 위해 연결 지점(`get_llm_client()`)만 미리 만들어두면, 다음 단계에서 추가할 코드의 범위가 명확해진다.
