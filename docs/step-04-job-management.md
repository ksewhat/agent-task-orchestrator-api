# Step 04. 비동기 Agent 작업 관리 - Job 상태 관리 기능

> 학습 일자: 2026-06-23
> 목표: LLM 작업을 즉시 실행하는 대신, Job으로 등록하고 상태를 조회할 수 있는 비동기 구조의 기반을 만든다.

---

## 1. 이번 단계에서 추가한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/job.py` | 신규 | `JobStatus`, `JobCreateRequest`, `JobResponse` 스키마 |
| `app/services/job_store.py` | 신규 | 인메모리 Job 저장소 (create / get / update) |
| `app/api/routes/job.py` | 신규 | `POST /jobs`, `GET /jobs/{job_id}` 라우터 |
| `app/main.py` | 수정 | job 라우터 등록 |
| `README.md` | 수정 | Job API 테스트 방법 추가 |

현재 단계에서 Job은 항상 `pending` 상태로 등록된다.
백그라운드 실행과 LLM 연동은 다음 단계에서 붙인다.

---

## 2. 왜 즉시 실행 대신 Job 패턴을 사용하는가

`POST /agent/plan`처럼 즉시 LLM을 호출해서 결과를 반환하는 방식은 단순하지만 한계가 있다.

**LLM 응답 시간 문제**
LLM 호출은 수 초에서 길게는 수십 초가 걸린다. 클라이언트가 그 시간 동안 응답을 기다려야 하는데, 네트워크가 끊기거나 타임아웃이 발생하면 결과를 잃게 된다.

**여러 작업 병렬 처리**
사용자가 여러 Agent 작업을 동시에 요청하면, 순차적으로 처리하는 방식은 뒤에 있는 요청이 앞 요청이 끝날 때까지 기다려야 한다.

**작업 추적과 재조회**
결과를 즉시 반환하면 나중에 다시 볼 수 없다. Job 패턴을 쓰면 job_id로 언제든지 상태와 결과를 다시 조회할 수 있다.

Job 패턴의 흐름:

```
클라이언트: POST /jobs          → 즉시 202 반환 (job_id 포함)
서버:       Job을 PENDING으로 등록
백그라운드: LLM 실행 → RUNNING → COMPLETED / FAILED 로 상태 변경
클라이언트: GET /jobs/{job_id}  → 현재 상태 + 결과 조회
```

이번 단계에서는 맨 위 두 줄(등록과 조회)만 구현했다.

---

## 3. HTTP 202 Accepted를 사용하는 이유

```python
@router.post("", response_model=JobResponse, status_code=202)
```

HTTP 상태 코드의 의미:

| 코드 | 의미 |
|------|------|
| 200 OK | 요청이 처리됐고 결과가 있다 |
| 201 Created | 리소스가 생성됐다 |
| **202 Accepted** | 요청을 접수했지만 아직 처리가 완료되지 않았다 |

`POST /jobs`는 Job을 "등록"할 뿐, LLM 실행이 완료된 것이 아니다. 그래서 202가 더 정확한 표현이다. 클라이언트에게 "요청은 받았는데 결과는 나중에 확인해"라는 의미를 HTTP 코드 레벨에서 전달할 수 있다.

---

## 4. 인메모리 저장소 설계

```python
_store: dict[str, JobResponse] = {}
```

모듈 레벨에 딕셔너리를 두면, 서버가 실행되는 동안 모든 요청이 같은 딕셔너리를 공유한다. 서버가 재시작되면 데이터는 사라진다.

현재 단계에서 이 방식을 쓰는 이유:
- DB 없이 빠르게 구조를 검증할 수 있다.
- 코드가 단순해서 흐름을 이해하기 쉽다.
- 나중에 Redis나 PostgreSQL로 교체할 때 함수 인터페이스(`create_job`, `get_job`, `update_job_status`)만 바꾸면 된다.

저장소 접근을 직접 딕셔너리 조작이 아니라 함수를 통해서만 하게 만든 것이 핵심이다. 라우터가 `_store`에 직접 접근하지 않고 `job_store.create_job()`을 호출하기 때문에, 나중에 저장소 구현을 바꿔도 라우터는 건드리지 않아도 된다.

---

## 5. `update_job_status()` 함수를 미리 만든 이유

이번 단계에서는 이 함수를 아직 호출하지 않는다. 그런데 왜 미리 만들었을까?

다음 단계에서 백그라운드 실행을 붙일 때, 이 함수가 필요해진다. 지금 인터페이스를 정해두면 다음 단계에서 저장소 코드를 다시 건드리지 않아도 된다. 또, 코드를 읽는 사람이 "다음에 이 함수를 여기서 쓰겠구나"를 미리 알 수 있다.

Pydantic v2의 `model_copy(update={...})`를 사용해서 기존 객체를 직접 변경하지 않고 새 객체를 만들어 저장한다. Pydantic 모델은 기본적으로 불변(immutable)이기 때문에 이 방식이 올바르다.

```python
_store[job_id] = job.model_copy(update={
    "status": status,
    "result": result,
    "error": error,
    "updated_at": datetime.now(timezone.utc),
})
```

---

## 6. `JobStatus`를 `str, Enum`으로 정의한 이유

```python
class JobStatus(str, Enum):
    PENDING = "pending"
```

`str`을 상속하면 두 가지 장점이 생긴다.

첫째, FastAPI가 JSON으로 직렬화할 때 `"pending"` 같은 문자열로 자동 변환된다. `str`을 상속하지 않으면 Enum 객체가 그대로 직렬화돼서 `{"status": 0}` 같은 예상치 못한 형태가 나올 수 있다.

둘째, `job.status == "pending"` 같은 문자열 비교가 가능해진다.

---

## 7. `result` 필드를 `AgentPlanResponse | None`으로 미리 정의한 이유

현재는 항상 `null`이지만, Swagger UI에서 응답 구조를 보면 "나중에 여기에 Agent 계획 결과가 들어온다"는 것을 바로 알 수 있다.

스키마를 미리 정의해두면 프론트엔드 개발자나 팀원이 API 문서만 보고도 다음 단계를 예측할 수 있다.

---

## 8. 다음 단계에서 할 것

이번 단계에서 Job 생성과 조회 구조를 만들었다. 다음 단계에서 아래를 추가한다.

- **백그라운드 실행**: FastAPI의 `BackgroundTasks` 또는 `asyncio`를 활용해 Job 등록 즉시 LLM 실행을 백그라운드로 시작
- **상태 전환**: `PENDING → RUNNING → COMPLETED / FAILED`
- **결과 저장**: LLM 실행 완료 후 `result` 필드에 `AgentPlanResponse` 저장
- **에러 저장**: LLM 실패 시 `error` 필드에 메시지 저장

이번 단계에서 만든 `update_job_status()` 함수와 `JobStatus` Enum이 다음 단계의 핵심 재료가 된다.

---

## 9. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| Job 패턴 | 긴 작업을 즉시 반환 대신 ID로 추적하는 비동기 설계 |
| HTTP 202 | "접수됨, 아직 처리 중" 을 의미하는 상태 코드 |
| 인메모리 저장소 | 빠른 검증용, 함수 인터페이스로 분리해 나중에 교체 가능 |
| `str, Enum` | Pydantic/FastAPI에서 JSON 직렬화가 올바르게 동작 |
| `model_copy(update={})` | Pydantic v2에서 불변 모델의 일부 필드를 수정하는 올바른 방법 |
