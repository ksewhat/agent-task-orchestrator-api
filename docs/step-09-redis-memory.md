# Step 09. Redis 기반 단기 메모리 큐 추가

> 학습 일자: 2026-06-26
> 목표: Agent가 최근 작업 흐름을 기억할 수 있도록 Redis List 기반 메모리 큐를 추가한다.

---

## 1. 이번 단계에서 추가/수정한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/memory.py` | 신규 | MemoryEvent, MemoryListResponse 스키마 |
| `app/services/memory_store.py` | 신규 | Redis List 기반 push/read 로직 |
| `app/api/routes/memory.py` | 신규 | `GET /agent/memory` 엔드포인트 |
| `app/core/config.py` | 수정 | `memory_max_size` 설정 추가 |
| `app/services/agent_runner.py` | 수정 | Worker 실행 흐름에 메모리 이벤트 push |
| `app/api/routes/agent_job.py` | 수정 | job 생성 시 `job_created` 이벤트 push |
| `app/api/routes/agent.py` | 수정 | 동기 plan 실행 시 `plan_generated/failed` 이벤트 push |
| `app/main.py` | 수정 | memory 라우터 등록 |

기존 기능의 API 응답 형태는 변경되지 않았다.

---

## 2. Redis History vs PostgreSQL History — 역할 비교

| 항목 | Redis 메모리 큐 | PostgreSQL History |
|------|----------------|-------------------|
| 목적 | Agent의 최근 작업 흐름 참고 | 완료된 작업의 장기 이력 보관 |
| 보관 기간 | 최근 N개 이벤트만 (자동 삭제) | 영구 저장 |
| 저장 단위 | 이벤트 (상태 변화 하나하나) | 완료된 요청 하나 |
| 접근 방식 | `GET /agent/memory` | `GET /history` |
| 사용 목적 | "직전에 무슨 일이 있었나?" | "지금까지 몇 번 성공했나?" |

이 두 저장소는 역할이 다르기 때문에 같은 요청에 대해 둘 다 기록될 수 있다.

---

## 3. Redis List — 왜 List를 선택했나

Redis는 여러 자료구조를 지원한다: String, Hash, List, Set, Sorted Set 등.

메모리 큐에 List를 선택한 이유:
- **순서 보장**: List는 삽입 순서를 유지한다. 이벤트가 발생한 순서대로 저장된다.
- **LPUSH + LTRIM 조합**: 새 이벤트를 앞에 넣고, 오래된 것을 자동으로 잘라낼 수 있다.
- **LRANGE로 범위 조회**: 인덱스로 최근 N개를 바로 꺼낼 수 있다.

---

## 4. LPUSH + LTRIM 패턴 — 고정 크기 큐 구현

```python
_redis.lpush(MEMORY_KEY, json.dumps(event))  # 앞에 삽입
_redis.ltrim(MEMORY_KEY, 0, settings.memory_max_size - 1)  # 크기 제한
```

**LPUSH**: 리스트의 왼쪽(앞)에 새 항목을 삽입한다. 실행할 때마다 가장 최신 이벤트가 index 0 자리를 차지한다.

**LTRIM**: 리스트를 지정한 범위로 잘라낸다. `LTRIM key 0 49`는 0번부터 49번까지 50개만 남기고 나머지를 삭제한다. LPUSH 직후 LTRIM을 호출하면 자동으로 오래된 이벤트가 제거된다.

결과적으로 이 두 명령의 조합이 "최신 N개만 유지하는 링 버퍼(ring buffer)"처럼 동작한다.

---

## 5. LRANGE — 최근 이벤트 읽기

```python
raw_items = _redis.lrange(MEMORY_KEY, 0, limit - 1)
```

`LRANGE key start stop`: 인덱스 `start`부터 `stop`까지의 항목을 반환한다 (양 끝 포함). index 0이 가장 최신 이벤트이므로 `LRANGE agent:memory 0 19`는 최신 20개를 반환한다.

반환값은 `bytes` 타입의 리스트다. `json.loads()`로 각 항목을 dict로 역직렬화한다.

---

## 6. JSON 직렬화 — 이벤트를 문자열로 저장하는 이유

Redis List의 각 항목은 문자열(또는 bytes)이어야 한다. Python dict는 직접 저장할 수 없다.

```python
# 저장: dict → JSON 문자열
json.dumps(event, ensure_ascii=False)

# 읽기: JSON 문자열 → dict
json.loads(item)
```

`ensure_ascii=False`: 기본값(`True`)이면 한글 같은 비ASCII 문자가 `\uXXXX` 형태로 이스케이프된다. `False`로 설정하면 원래 문자 그대로 저장되어 가독성이 높아진다.

---

## 7. 이벤트 흐름 — 어느 시점에 무엇이 기록되는가

```
POST /agent/jobs
  ↓
  [job_created]  ← agent_job.py 라우터에서 push
  ↓ (RQ 큐에 등록, 202 반환)

RQ Worker가 작업 처리 시작
  ↓
  [job_running]  ← agent_runner.py에서 RUNNING 전환 직후 push
  ↓
  LLM 호출 (OpenAI API)
  ↓
  성공 → [job_succeeded]  ← goal, step_count 포함
  실패 → [job_failed]     ← error 메시지 포함

POST /agent/plan (동기)
  ↓
  성공 → [plan_generated]
  실패 → [plan_failed]
```

하나의 비동기 Job에 대해 최소 3개의 이벤트가 기록된다: `job_created` → `job_running` → `job_succeeded` 또는 `job_failed`

---

## 8. 에러 처리 — 메모리 push는 선택적 기능

```python
def push_event(...) -> None:
    try:
        ...
    except Exception:
        pass  # Redis 오류는 무시
```

메모리 큐는 "있으면 좋지만 없어도 되는" 기능이다. Redis가 꺼져 있거나 네트워크 문제가 있어도 Agent Job 실행이나 API 응답에 영향을 주지 않아야 한다. 그래서 `push_event()`는 모든 예외를 조용히 삼킨다.

`get_recent()`도 마찬가지다. Redis 연결 실패 시 빈 리스트를 반환해서 `GET /agent/memory`가 500 에러 대신 정상적으로 빈 응답을 반환한다.

---

## 9. `dict[str, Any]` 타입 힌트

```python
from typing import Any

payload: dict[str, Any]
```

`dict[str, Any]`는 "키는 문자열이고, 값은 어떤 타입이든 허용"이라는 의미다. 이벤트 타입마다 payload의 내용이 다르기 때문에 (goal이 있는 것도, error가 있는 것도 있으므로) 고정된 타입을 쓸 수 없다. `Any`는 Python의 타입 검사를 이 필드에 대해 포기하겠다는 표시다.

---

## 10. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| Redis List | 순서가 있는 큐. LPUSH(앞 삽입) + LRANGE(범위 조회) |
| LPUSH + LTRIM | 고정 크기 링 버퍼 패턴 — 오래된 이벤트 자동 삭제 |
| JSON 직렬화 | Redis에는 문자열만 저장 가능 → `json.dumps` / `json.loads` |
| 비치명적 에러 처리 | 메모리 push 실패가 메인 흐름을 중단하지 않도록 try/except |
| 역할 분리 | Redis(단기 맥락) vs PostgreSQL(장기 이력) |

---

## 11. 다음 단계에서 할 것

- Agent가 실행 시점에 메모리 큐를 읽어 최근 맥락을 LLM 프롬프트에 포함
- 메모리 이벤트에 TTL 추가 (예: 24시간 후 자동 만료)
- 이벤트 타입별 필터 조회 (`GET /agent/memory?event_type=job_failed`)
