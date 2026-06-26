# Step 09. Redis 기반 Agent Memory Queue 및 프롬프트 반영

> 학습 일자: 2026-06-26
> 목표: Agent가 최근 작업 흐름을 Redis에 기록하고, LLM 호출 시 그 맥락을 프롬프트에 반영해 연속성을 갖추도록 한다.

---

## 1. 이번 단계에서 추가/수정한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/memory.py` | 신규 | MemoryEvent, MemoryListResponse 스키마 |
| `app/services/memory_store.py` | 신규 | Redis List 기반 push/read/build_memory_context |
| `app/api/routes/memory.py` | 신규 | `GET /agent/memory` 엔드포인트 |
| `app/core/config.py` | 수정 | `memory_max_size` 설정 추가 |
| `app/services/llm_client.py` | 수정 | `generate_agent_plan()`에 `memory_context` 파라미터 추가 |
| `app/services/agent_runner.py` | 수정 | Worker 흐름에 이벤트 push + LLM 호출 전 메모리 컨텍스트 주입 |
| `app/api/routes/agent.py` | 수정 | 동기 plan 실행에 이벤트 push + 메모리 컨텍스트 주입 |
| `app/api/routes/agent_job.py` | 수정 | job 생성 시 `job_created` 이벤트 push |
| `app/main.py` | 수정 | memory 라우터 등록 |

기존 API 응답 형태는 변경되지 않았다.

---

## 2. 이 단계에서 해결한 두 가지 문제

**문제 1 — 메모리가 기록은 되지만 활용되지 않는다:**
Step 09 초기 구현에서 Redis 메모리 큐에 이벤트를 저장하는 기능을 추가했지만, LLM을 호출할 때 그 데이터를 읽지 않았다. 메모리는 조회용 기록에 머물고 있었다.

**문제 2 — Agent는 매 요청을 독립적으로 처리한다:**
사용자가 "Python 웹 스크래퍼 만들기"를 이미 요청했는데 다음에 "오류 처리 추가"를 요청하면, LLM은 이전 요청과의 연관성을 알 수 없다.

**해결:** LLM 호출 직전에 Redis 메모리 큐를 읽어 최근 완료 이벤트를 프롬프트에 포함한다.

---

## 3. 전체 동작 흐름

```
POST /agent/jobs (또는 POST /agent/plan)
  ↓
  [job_created 이벤트 → Redis]
  ↓
RQ Worker 실행 시작
  ↓
  [job_running 이벤트 → Redis]
  ↓
  build_memory_context() 호출
  ├─ Redis에서 최근 완료 이벤트 조회 (job_succeeded, job_failed 등)
  └─ "[최근 작업 맥락]\n- 성공 | ..." 형태의 텍스트 생성
  ↓
  generate_agent_plan(user_request, context, memory_context) 호출
  ↓
  LLM 프롬프트 구성:
    사용자 요청: {user_request}
    추가 컨텍스트: {context}        ← 사용자가 직접 제공한 컨텍스트 (선택)
    [최근 작업 맥락]                ← Redis 메모리에서 읽어온 내용 (선택)
    - 성공 | "이전 요청" → 목표: "..."
    - 실패 | "다른 요청" → 오류: "..."
  ↓
  LLM 응답 → AgentPlanResponse
  ↓
  [job_succeeded 이벤트 → Redis]
  PostgreSQL에 결과 저장
```

---

## 4. `build_memory_context()` — 메모리를 프롬프트 텍스트로 변환

```python
def build_memory_context(limit: int = 5) -> str | None:
    all_events = get_recent(limit * 3)
    meaningful = [e for e in all_events if e.get("event_type") in _PROMPT_RELEVANT_TYPES][:limit]

    if not meaningful:
        return None

    lines = []
    for event in meaningful:
        user_req = str(payload.get("user_request", ""))[:60]  # 길이 제한
        if event_type in (EVENT_JOB_SUCCEEDED, EVENT_PLAN_GENERATED):
            lines.append(f'- 성공 | "{user_req}" → 목표: "{goal}" ({step_count}단계)')
        elif event_type in (EVENT_JOB_FAILED, EVENT_PLAN_FAILED):
            lines.append(f'- 실패 | "{user_req}" → 오류: "{error}"')

    return "[최근 작업 맥락]\n" + "\n".join(lines)
```

**포함 이벤트 타입:** `job_succeeded`, `job_failed`, `plan_generated`, `plan_failed`
**제외 이벤트 타입:** `job_created`, `job_running` (중간 상태, LLM에 유용하지 않음)

**길이 제한의 이유:** LLM 프롬프트 토큰은 유한하다. 긴 user_request나 error 메시지를 무제한 넣으면 실제 요청 처리를 위한 토큰이 줄어든다. 각 필드를 60~80자로 제한해 "흐름 파악에 필요한 최소한"만 포함한다.

---

## 5. `generate_agent_plan()` 시그니처 변경

```python
# 변경 전
def generate_agent_plan(user_request: str, context: str | None = None)

# 변경 후
def generate_agent_plan(
    user_request: str,
    context: str | None = None,
    memory_context: str | None = None,
)
```

`memory_context`가 `None`이면 기존과 동일하게 동작한다. Redis가 없거나 과거 이벤트가 없으면 `build_memory_context()`가 `None`을 반환하므로 프롬프트에 아무것도 추가되지 않는다.

---

## 6. 프롬프트 구조 — 세 가지 입력의 역할 분리

```
system_prompt  ← 역할 정의, 출력 형식 지시 (고정)
user_message:
  사용자 요청: {user_request}         ← 이번 요청 (필수)
  추가 컨텍스트: {context}            ← 사용자가 직접 전달한 배경 (선택)
  [최근 작업 맥락]                    ← Redis 메모리에서 자동 주입 (선택)
  - 성공 | ...
  - 실패 | ...
```

세 입력은 목적이 다르다:
- `user_request`: 이번에 해결할 과제
- `context`: 사용자가 직접 알려주는 배경 정보
- `memory_context`: 시스템이 자동으로 읽어온 최근 흐름

---

## 7. 동기 경로와 비동기 경로 — 같은 방식으로 주입

**동기 (`POST /agent/plan` → `agent.py`):**
```python
memory_context = build_memory_context()
result = generate_agent_plan(request.user_request, request.context, memory_context)
```

**비동기 (`POST /agent/jobs` → RQ Worker → `agent_runner.py`):**
```python
memory_context = build_memory_context()
result = generate_agent_plan(job.user_request, job.context, memory_context)
```

두 경로 모두 LLM 호출 직전에 동일한 `build_memory_context()`를 호출한다. Redis 메모리 큐는 경로 구분 없이 동일한 이벤트를 공유한다.

---

## 8. Redis History vs PostgreSQL History — 역할 비교

| 항목 | Redis 메모리 큐 | PostgreSQL History |
|------|----------------|-------------------|
| 목적 | Agent 실행 시 최근 맥락 참고 | 완료된 작업의 장기 이력 보관 |
| 보관 기간 | 최근 N개만 (자동 삭제) | 영구 저장 |
| 저장 단위 | 이벤트 하나하나 | 완료된 요청 하나 |
| LLM에 활용 | O (프롬프트에 주입) | X (조회용) |
| 접근 API | `GET /agent/memory` | `GET /history` |

---

## 9. LPUSH + LTRIM 패턴 — 고정 크기 큐

```python
_redis.lpush(MEMORY_KEY, json.dumps(event, ensure_ascii=False))  # 앞에 삽입
_redis.ltrim(MEMORY_KEY, 0, settings.memory_max_size - 1)        # 크기 제한
```

`LPUSH`는 리스트 왼쪽에 새 항목을 삽입한다. 가장 최신 이벤트가 항상 index 0에 있다.
`LTRIM`은 지정 범위 밖의 항목을 즉시 삭제한다. 매번 삽입 후 실행하면 최대 크기가 유지된다.

---

## 10. 에러 처리 원칙

**메모리 push**: `try/except` 안에서 조용히 실패. Redis 오류가 Job 실행을 멈추지 않는다.
**메모리 read (`build_memory_context`)**: `get_recent()` 내부에서 예외 처리. Redis 없으면 `None` 반환. LLM은 메모리 없이 기존 방식으로 동작.

메모리는 "있으면 더 좋은" 기능이지, 핵심 기능에 의존하면 안 된다.

---

## 11. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| Redis List | LPUSH로 앞에 삽입, LTRIM으로 크기 고정 |
| `build_memory_context()` | 완료 이벤트만 선별 → 길이 제한 → 프롬프트 텍스트 생성 |
| `memory_context` 파라미터 | `None`이면 기존과 동일. 하위 호환성 유지 |
| 프롬프트 주입 위치 | 사용자 메시지 끝. 시스템 프롬프트 오염 없음 |
| 비치명적 설계 | Redis 없어도 LLM 호출은 정상 진행 |

---

## 12. 다음 단계에서 할 것

- 이벤트 타입별 필터 조회 (`GET /agent/memory?event_type=job_failed`)
- 메모리 이벤트에 TTL 추가 (예: 24시간 후 자동 만료, `EXPIRE` 명령)
- Agent가 메모리 맥락을 더 정교하게 활용하는 프롬프트 튜닝
