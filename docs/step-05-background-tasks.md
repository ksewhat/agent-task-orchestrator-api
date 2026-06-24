# Step 05. FastAPI BackgroundTasks로 비동기 LLM 실행 연결

> 학습 일자: 2026-06-24
> 목표: Job 등록 즉시 job_id를 반환하고, LLM 실행은 백그라운드에서 자동으로 진행되게 만든다.

---

## 1. 이번 단계에서 추가한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/job.py` | 수정 | `COMPLETED → SUCCEEDED` 변경, `JobResultResponse` 추가 |
| `app/services/agent_runner.py` | 신규 | 백그라운드 LLM 실행 함수 |
| `app/api/routes/agent_job.py` | 신규 | `POST /agent/jobs`, `GET /agent/jobs/{job_id}`, `GET /agent/jobs/{job_id}/result` |
| `app/main.py` | 수정 | `agent_job` 라우터 등록 |
| `README.md` | 수정 | Agent Jobs API 테스트 흐름 추가 |

---

## 2. 전체 동작 흐름

```
클라이언트: POST /agent/jobs
  │
  ▼
agent_job.py (라우터)
  │  job_store.create_job() → PENDING 상태로 저장
  │  background_tasks.add_task(run_agent_plan_job, job_id)
  │  즉시 202 반환 (job_id 포함)
  │
  ├─── 클라이언트가 즉시 응답을 받음
  │
  └─── 서버 백그라운드에서 실행됨 ────────────────────────┐
                                                          ▼
                                              agent_runner.py
                                                RUNNING으로 상태 변경
                                                generate_agent_plan() 호출
                                                  성공 → SUCCEEDED + result 저장
                                                  실패 → FAILED + error 저장

클라이언트: GET /agent/jobs/{job_id}/result
  → 완료 여부에 따라 result 또는 error 반환
```

---

## 3. FastAPI BackgroundTasks의 동작 원리

```python
@router.post("")
def create_agent_job(request: JobCreateRequest, background_tasks: BackgroundTasks):
    job = job_store.create_job(...)
    background_tasks.add_task(run_agent_plan_job, job.job_id)  # 등록만 함
    return job  # 즉시 반환
```

`background_tasks.add_task(fn, arg)`는 함수를 "실행"하는 것이 아니라 "등록"하는 것이다. 실제 실행은 HTTP 응답이 클라이언트에게 전송된 직후 시작된다.

FastAPI의 BackgroundTasks는 별도 프로세스나 스레드 풀을 쓰는 것이 아니라, 같은 서버 프로세스 내에서 응답 이후에 순차적으로 실행된다. 따라서 간단한 작업에는 적합하지만, 매우 오래 걸리는 작업이나 고부하 환경에서는 Celery 같은 전용 작업 큐가 필요하다.

---

## 4. `agent_runner.py`를 별도 파일로 분리한 이유

백그라운드에서 실행할 로직을 라우터 안에 직접 넣을 수도 있다.

```python
# 이렇게 하면 안 된다 (예시)
def _run_in_background(job_id):
    ...

@router.post("")
def create_agent_job(request, background_tasks):
    background_tasks.add_task(_run_in_background, job_id)
```

하지만 이렇게 하면 라우터 파일이 LLM 호출 로직까지 담게 된다. 역할이 섞이는 문제가 생긴다.

`agent_runner.py`로 분리하면:
- 라우터는 "HTTP 요청을 받고 작업을 등록"하는 역할만 한다.
- runner는 "작업을 실행하고 결과를 저장"하는 역할만 한다.
- runner를 직접 테스트하거나 다른 곳에서 재사용하기 쉬워진다.

---

## 5. 예외 처리 설계

```python
try:
    result = generate_agent_plan(job.user_request, job.context)
    job_store.update_job_status(job_id, JobStatus.SUCCEEDED, result=result)

except (LLMClientNotConfiguredError, LLMCallError, LLMResponseParseError) as e:
    job_store.update_job_status(job_id, JobStatus.FAILED, error=str(e))

except Exception as e:
    job_store.update_job_status(
        job_id, JobStatus.FAILED, error=f"예기치 않은 오류가 발생했습니다: {e}"
    )
```

백그라운드 태스크에서 예외가 발생해도 FastAPI는 기본적으로 조용히 무시한다. 클라이언트에게 HTTP 에러를 전달할 수 없는 상황이기 때문이다. 그래서 모든 예외를 `try/except`로 잡아서 Job 상태를 `FAILED`로 저장하고 에러 메시지를 남긴다. 클라이언트는 나중에 result API를 통해 실패 이유를 확인할 수 있다.

마지막 `except Exception`은 예상치 못한 오류까지 잡기 위한 안전망이다. 이게 없으면 예기치 않은 오류 발생 시 Job이 영원히 `running` 상태로 남는다.

---

## 6. `GET /agent/jobs/{job_id}/result` 라우트가 `GET /agent/jobs/{job_id}`와 충돌하지 않는 이유

FastAPI는 경로 세그먼트 수가 다른 라우트를 자동으로 구분한다.

- `/agent/jobs/{job_id}` → 경로 4개 세그먼트
- `/agent/jobs/{job_id}/result` → 경로 5개 세그먼트

`/agent/jobs/abc-123/result`라는 요청이 들어오면, FastAPI는 5개 세그먼트 패턴인 `/{job_id}/result`에 먼저 매칭시킨다. `{job_id}`가 `abc-123/result`라고 해석되지 않는다. UUID 기반 job_id이면 슬래시가 포함되지 않으니 충돌 위험이 없다.

---

## 7. `COMPLETED` → `SUCCEEDED`로 변경한 이유

이전 단계에서는 `COMPLETED`를 사용했지만, 이번 단계에서 `SUCCEEDED`로 바꿨다.

`COMPLETED`는 "완료됨"이라는 중립적인 의미다. 하지만 `SUCCEEDED`는 "성공적으로 완료됨"을 명확히 표현한다. 성공과 실패가 모두 작업 완료 상태인데, `COMPLETED`와 `FAILED`를 같이 쓰면 완료 = 성공이라는 혼동이 생길 수 있다.

`SUCCEEDED / FAILED` 쌍으로 쓰면 의미가 더 명확하다.

---

## 8. BackgroundTasks의 한계와 다음 단계

FastAPI BackgroundTasks는 가볍고 설정이 간단하지만 제약이 있다.

| 항목 | BackgroundTasks | Celery + Redis |
|------|----------------|----------------|
| 설정 복잡도 | 낮음 | 높음 |
| 서버 재시작 시 작업 유실 | O (유실됨) | X (큐에 보존) |
| 작업 진행률 추적 | 어려움 | 가능 |
| 분산 처리 | X | O |
| 포트폴리오/학습 용도 | 적합 | 오버킬 |

지금 단계에서는 BackgroundTasks로 충분하다. 실제 운영 서비스라면 Celery나 ARQ 같은 작업 큐로 전환이 필요하다.

---

## 9. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| `BackgroundTasks.add_task()` | 응답 전송 후 실행할 함수를 등록 |
| 상태 전환 | `pending → running → succeeded / failed` |
| 백그라운드 예외 처리 | `try/except`로 전부 잡아 Job에 저장해야 클라이언트가 알 수 있음 |
| `agent_runner.py` 분리 | 실행 로직과 HTTP 라우팅 분리 |
| `JobResultResponse` | 결과 조회 전용 슬림 응답 스키마 |
