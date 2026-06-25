# Step 08. Redis + RQ 기반 비동기 작업 큐 전환

> 학습 일자: 2026-06-25
> 목표: FastAPI BackgroundTasks 대신 Redis + RQ로 Agent Job 실행을 분리한다.

---

## 1. 이번 단계에서 추가/수정한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/core/config.py` | 수정 | `redis_url` 설정 추가 |
| `app/services/task_queue.py` | 신규 | Redis 연결 및 RQ Queue 초기화 |
| `app/api/routes/agent_job.py` | 수정 | `BackgroundTasks` 제거, `task_queue.enqueue()` 로 교체 |
| `app/services/agent_runner.py` | 수정 | 독스트링만 변경 (로직 동일) |
| `worker.py` | 신규 | RQ Worker 진입점 (프로젝트 루트) |
| `requirements.txt` | 수정 | `redis`, `rq` 추가 |
| `.env.example` | 수정 | `REDIS_URL` 항목 추가 |
| `README.md` | 수정 | Redis 준비 및 Worker 실행 방법 추가 |

`agent_runner.py`의 `run_agent_plan_job()` 함수 자체는 변경되지 않았다. 이 함수는 PostgreSQL에 직접 쓰기 때문에 어떤 방식으로 호출해도 결과가 동일하다.

---

## 2. BackgroundTasks vs RQ — 무엇이 달라졌는가

| 항목 | BackgroundTasks (Step 05) | RQ (Step 08) |
|------|--------------------------|--------------|
| 실행 위치 | API 서버 프로세스 내부 | 별도 Worker 프로세스 |
| 서버 재시작 시 큐 유지 | X (유실) | O (Redis에 보존) |
| 여러 Worker 수평 확장 | X | O (Worker를 여러 개 띄울 수 있음) |
| 작업 상태 추적 | 불가 | RQ 대시보드로 가능 |
| 실행 중 API 서버 부하 | 함께 받음 | 분리됨 |
| 설정 복잡도 | 낮음 | 중간 |

핵심 차이는 "실행 공간"이다. BackgroundTasks는 API 서버 안에서 실행되지만, RQ Worker는 완전히 분리된 프로세스에서 실행된다.

---

## 3. 전체 동작 흐름

```
클라이언트
  │  POST /agent/jobs
  ▼
API 서버 (app/api/routes/agent_job.py)
  │  job_store.create_job()     → PostgreSQL에 PENDING 상태로 저장
  │  task_queue.enqueue(run_agent_plan_job, job_id)
  │                             → Redis "agent" 큐에 작업 등록
  │  즉시 202 반환 (job_id 포함)
  │
Redis (agent 큐)
  │  작업 대기 중...
  ▼
RQ Worker (worker.py)
  │  큐에서 작업 꺼냄
  │  run_agent_plan_job(job_id) 실행
  │    job_store.update_job_status() → RUNNING
  │    generate_agent_plan()         → OpenAI API 호출
  │    job_store.update_job_status() → SUCCEEDED + result
  │    history_store.add_entry()     → PostgreSQL에 히스토리 저장
  ▼
PostgreSQL
  → 결과 영구 저장

클라이언트
  │  GET /agent/jobs/{job_id}/result
  └─ PostgreSQL에서 결과 조회
```

---

## 4. `task_queue.py` — Queue 초기화

```python
_redis_conn = Redis.from_url(settings.redis_url)
task_queue = Queue(name="agent", connection=_redis_conn)
```

`Redis.from_url()`은 연결을 즉시 맺지 않는다. 실제 TCP 연결은 처음으로 Redis에 명령을 보낼 때(lazy) 맺어진다. 그래서 Redis가 꺼져 있어도 서버가 시작되는 데는 문제없다. 에러는 `task_queue.enqueue()`를 호출하는 시점에 발생한다.

`Queue(name="agent")`: Redis 안에서 `rq:queue:agent`라는 키로 관리된다. Worker가 처리할 큐 이름과 반드시 일치해야 한다.

---

## 5. `task_queue.enqueue(fn, arg)` — 작업 등록 방식

```python
task_queue.enqueue(run_agent_plan_job, job.job_id)
```

RQ는 함수 객체(`run_agent_plan_job`)와 인수(`job.job_id`)를 직렬화해서 Redis에 저장한다. Worker는 이 데이터를 꺼내서 `run_agent_plan_job(job.job_id)`를 실행한다.

RQ가 함수를 직렬화할 때 사용하는 정보는 **함수의 모듈 경로**다. `app.services.agent_runner.run_agent_plan_job`이라는 문자열이 Redis에 저장된다. Worker가 이 작업을 꺼낼 때 같은 경로로 import해서 실행한다.

이 때문에 Worker 실행 시 프로젝트 루트가 Python path에 포함되어야 한다. `python worker.py`를 프로젝트 루트에서 실행하면 자동으로 해결된다.

---

## 6. `worker.py` — Worker 진입점 설계

```python
from dotenv import load_dotenv
load_dotenv()  # 반드시 가장 먼저 실행

from redis import Redis
from rq import Worker, Queue
from app.core.config import settings
```

`load_dotenv()`를 가장 먼저 호출하는 이유: Worker는 API 서버와 별도 프로세스이므로, `.env` 파일에서 환경변수를 직접 읽어야 한다. `load_dotenv()` 이후에 import를 해야 `settings.redis_url`과 `settings.database_url`이 올바른 값으로 설정된다.

`worker.work(with_scheduler=True)`: Worker를 계속 실행 상태로 유지하며 큐를 감시한다. 새 작업이 들어오면 즉시 처리한다. `Ctrl+C`를 누르면 현재 처리 중인 작업을 완료하고 종료된다.

---

## 7. Redis 큐에 작업이 쌓였을 때 Worker가 없으면?

Worker 없이 `POST /agent/jobs`를 호출하면 작업이 Redis 큐에 쌓인다. Job 상태는 `pending`으로 유지된다.

이후 Worker를 시작하면 쌓여 있던 작업들을 순서대로 처리한다. 이것이 BackgroundTasks와 다른 중요한 차이다. BackgroundTasks는 서버가 종료되면 처리되지 않은 작업이 사라지지만, RQ는 Redis에 보존된다.

---

## 8. 에러 처리 — Redis 연결 실패 시

```python
try:
    task_queue.enqueue(run_agent_plan_job, job.job_id)
except Exception as e:
    job_store.update_job_status(job.job_id, JobStatus.FAILED, error=f"작업 큐 등록 실패: {e}")
    raise HTTPException(status_code=503, detail="작업 큐에 연결할 수 없습니다.")
```

Redis가 꺼져 있는 상태에서 enqueue를 시도하면 연결 에러가 발생한다. 이 에러를 잡아서 Job을 FAILED 상태로 저장하고 클라이언트에게 503을 반환한다. Job이 PENDING 상태로 방치되는 것보다 즉시 실패 처리하는 것이 더 명확하다.

---

## 9. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| 프로세스 분리 | API 서버와 Worker가 별도 프로세스로 완전히 분리됨 |
| Redis 큐 | 작업이 영구 보존되어 Worker 없이도 큐에 쌓임 |
| `enqueue(fn, arg)` | 함수 경로와 인수를 Redis에 직렬화해서 저장 |
| `load_dotenv()` 선행 | Worker는 독립 프로세스이므로 `.env` 로드가 최우선 |
| `run_agent_plan_job` 재사용 | 함수 로직 변경 없이 호출 방식만 교체 |

---

## 10. 다음 단계에서 할 것

- RQ 대시보드(`rq-dashboard`) 연동으로 작업 상태 시각화
- Worker 재시도 설정 (`job.retry(3)`) — 일시적 API 오류 대응
- 작업 타임아웃 설정 (`task_queue.enqueue(..., job_timeout=60)`)
- 여러 Worker 인스턴스 실행으로 병렬 처리 테스트
