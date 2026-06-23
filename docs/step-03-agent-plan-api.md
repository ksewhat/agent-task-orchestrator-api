# Step 03. AI Agent 계획 생성 API 구현

> 학습 일자: 2026-06-23
> 목표: 사용자의 자연어 요청을 LLM으로 처리해 구조화된 실행 계획 JSON을 반환하는 API를 만든다.

---

## 1. 이번 단계에서 추가한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/agent.py` | 신규 | 요청/응답 Pydantic 스키마 정의 |
| `app/api/routes/agent.py` | 신규 | `POST /agent/plan` 라우터 구현 |
| `app/services/llm_client.py` | 수정 | `generate_agent_plan()` 함수 및 예외 클래스 추가 |
| `app/core/config.py` | 수정 | `openai_model` 설정 추가 |
| `app/main.py` | 수정 | agent 라우터 등록 |
| `.env.example` | 수정 | `OPENAI_MODEL` 항목 추가 |
| `README.md` | 수정 | API 테스트 방법 추가 |

최종 엔드포인트: **POST /agent/plan**

---

## 2. 전체 요청 흐름

```
클라이언트
  │  POST /agent/plan {"user_request": "..."}
  ▼
app/api/routes/agent.py    ← 입력 검증, 에러 변환
  │  generate_agent_plan() 호출
  ▼
app/services/llm_client.py ← OpenAI API 호출, JSON 파싱
  │  AgentPlanResponse 반환
  ▼
app/schemas/agent.py       ← Pydantic 스키마 검증
  │
  ▼
클라이언트에 JSON 응답 반환
```

각 계층이 하는 일이 명확히 나뉜다. 라우터는 HTTP를, 서비스는 LLM을, 스키마는 데이터 형태를 담당한다.

---

## 3. Pydantic 스키마를 왜 별도 파일로 분리했는가

처음에는 router 파일 안에 그냥 클래스를 정의해도 되겠다고 생각했다. 하지만 스키마를 별도 파일로 분리하면 몇 가지 장점이 생긴다.

**재사용성**: 같은 스키마를 여러 라우터에서 임포트해서 쓸 수 있다.

**Swagger 자동화**: FastAPI는 Pydantic 모델을 읽어서 `/docs`에 요청/응답 형태를 자동으로 보여준다. `Field(description=..., examples=...)`를 잘 써두면 별도 API 문서 없이도 팀원이 바로 사용할 수 있는 문서가 만들어진다.

**테스트 용이성**: 스키마만 임포트해서 독립적으로 유효성 검사를 테스트할 수 있다.

---

## 4. LLM에게 JSON을 강제하는 방법

LLM은 기본적으로 자유롭게 텍스트를 생성한다. "JSON으로 줘"라고 프롬프트에만 쓰면 마크다운 코드블록으로 감싸거나, 설명 텍스트를 앞에 붙이거나, 가끔 JSON 형식을 어기는 경우가 있다.

이번에는 두 가지 방법을 함께 사용했다.

**1) System Prompt에서 명시적으로 지시**

```python
"반드시 JSON만 반환하라."
"마크다운 코드블록을 사용하지 말라."
"응답 필드는 goal, summary, steps, risks, next_action만 포함하라."
```

**2) OpenAI JSON mode 활성화**

```python
response_format={"type": "json_object"}
```

이 옵션을 설정하면 OpenAI 모델이 반드시 유효한 JSON만 반환하도록 강제된다. 마크다운 코드블록이나 추가 텍스트가 붙지 않는다. 단, System Prompt에 "JSON"이라는 단어가 반드시 포함되어 있어야 작동한다.

그래도 응답을 받은 뒤에는 `json.loads()`로 파싱하고, Pydantic으로 한 번 더 검증한다. LLM 응답을 무조건 신뢰하지 않는 방어적인 코딩이 중요하다.

---

## 5. 에러 처리 계층 설계

에러가 발생하는 지점과 HTTP 응답으로 변환하는 지점을 분리했다.

```
서비스 계층 (llm_client.py)
  └─ LLMClientNotConfiguredError  → API Key 없음
  └─ LLMCallError                 → OpenAI API 호출 실패
  └─ LLMResponseParseError        → JSON 파싱 or 스키마 불일치

라우터 계층 (agent.py)
  └─ LLMClientNotConfiguredError  → HTTP 503
  └─ LLMCallError                 → HTTP 502
  └─ LLMResponseParseError        → HTTP 502
```

서비스 계층에서는 OpenAI 내부 에러를 그대로 올리지 않고 의미 있는 커스텀 예외로 감싼다.

```python
try:
    response = client.chat.completions.create(...)
except OpenAIError as e:
    raise LLMCallError(f"OpenAI API 호출에 실패했습니다: {e}")
```

라우터는 서비스 계층의 예외만 알면 되고, OpenAI SDK 내부 구조는 신경 쓰지 않아도 된다. 나중에 OpenAI를 다른 LLM으로 바꿔도 라우터 코드는 그대로 쓸 수 있다.

---

## 6. 왜 router에서 직접 OpenAI를 호출하지 않는가

처음에는 라우터 함수 안에서 바로 `openai.chat.completions.create()`를 호출해도 될 것 같았다. 코드도 짧아지고 파일도 줄어드니까.

하지만 이렇게 하면 문제가 생긴다.

- 라우터가 HTTP 처리와 LLM 호출을 동시에 담당해서 역할이 섞인다.
- 나중에 LLM을 다른 모델로 바꾸거나 캐싱을 추가할 때 라우터를 직접 건드려야 한다.
- 같은 LLM 호출 로직을 다른 라우터에서도 써야 할 때 복붙이 생긴다.
- 테스트할 때 라우터 전체를 실행해야만 LLM 로직을 테스트할 수 있다.

서비스 계층을 분리하면 `generate_agent_plan()` 함수만 단독으로 테스트할 수 있고, 라우터는 HTTP 계층만 테스트하면 된다.

---

## 7. 서버 시작 시 API Key를 검증하지 않는 이유

`/health` API는 API Key 없이도 동작해야 한다. 서버 시작 시점에 Key를 강제하면, Key가 없는 환경에서는 서버 자체가 뜨지 않아서 `/health`도 응답할 수 없게 된다.

그래서 `get_llm_client()` 함수 내부에서 Key를 확인하고, Key가 없으면 `LLMClientNotConfiguredError`를 발생시키는 방식으로 설계했다.

```python
def get_llm_client():
    if not settings.openai_api_key:
        raise LLMClientNotConfiguredError("...")
    ...
```

서버는 항상 정상 시작되고, LLM 기능을 실제로 쓰려는 시점에만 에러가 발생한다.

---

## 8. `openai_model`을 settings에 넣은 이유

모델명을 코드에 하드코딩하면 나중에 `gpt-4o`나 다른 모델로 바꿀 때 코드를 직접 수정해야 한다. `.env`에서 관리하면 코드를 건드리지 않고 `.env`만 바꾸면 된다.

```env
OPENAI_MODEL=gpt-4o-mini
```

기본값을 `gpt-4o-mini`로 설정해뒀기 때문에, `.env`에 값이 없어도 동작한다.

---

## 9. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| Pydantic 스키마 분리 | 요청/응답 형태를 명시적으로 정의해 Swagger 자동화 |
| 서비스 계층 분리 | LLM 호출 로직을 라우터와 분리해 역할 명확화 |
| JSON mode | `response_format={"type": "json_object"}`로 JSON 강제 |
| 커스텀 예외 → HTTP 변환 | 서비스 예외를 라우터에서 HTTP 상태 코드로 변환 |
| 지연 검증 | API Key는 서버 시작이 아니라 실제 사용 시점에 검증 |

---

## 10. 다음 단계에서 할 것

- 테스트 코드 작성 (`pytest`, 서비스 계층 단독 테스트)
- LLM 응답에 대한 재시도 로직 (일시적 API 오류 대응)
- 요청/응답 로깅 추가
- 다양한 Agent Task 타입 추가 (`/agent/review`, `/agent/summarize` 등)
