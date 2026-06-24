# Step 06. Agent 요청 히스토리 기능

> 학습 일자: 2026-06-24
> 목표: Agent 요청의 결과 요약을 인메모리에 기록하고, 최근 히스토리를 조회할 수 있게 만든다.

---

## 1. 이번 단계에서 추가한 것

| 파일 | 변경 유형 | 내용 |
|------|----------|------|
| `app/schemas/history.py` | 신규 | `HistoryEntry`, `HistoryListResponse` 스키마 |
| `app/services/history_store.py` | 신규 | 인메모리 히스토리 저장소 (deque 기반) |
| `app/api/routes/history.py` | 신규 | `GET /history` 엔드포인트 |
| `app/services/agent_runner.py` | 수정 | 비동기 Job 완료 시 히스토리 기록 추가 |
| `app/api/routes/agent.py` | 수정 | 즉시 실행 API 완료 시 히스토리 기록 추가 |
| `app/main.py` | 수정 | history 라우터 등록 |
| `README.md` | 수정 | 히스토리 API 사용법 및 보안 주의사항 추가 |

---

## 2. 왜 전체 LLM 결과가 아니라 요약만 저장하는가

히스토리는 "무슨 요청을 했고 결과가 어땠나"를 빠르게 확인하는 용도다. 전체 결과를 저장하면 두 가지 문제가 생긴다.

**메모리 사용량**: LLM 응답은 텍스트 양이 많다. 히스토리에 전체 결과를 저장하면, 요청이 쌓일수록 메모리가 계속 늘어난다.

**민감정보 위험**: 전체 결과에는 사용자의 요청 내용도 포함되는데, 이 안에 민감한 정보가 있을 수 있다. 요약 정보만 저장하면 그 위험을 줄일 수 있다.

그래서 `goal`(목표 한 줄)과 `step_count`(단계 수)만 저장한다. 전체 결과는 Job 저장소에서 `GET /agent/jobs/{job_id}/result`로 조회할 수 있다.

---

## 3. `deque(maxlen=100)` 을 선택한 이유

```python
_store: deque[HistoryEntry] = deque(maxlen=100)
```

`maxlen`을 설정한 `deque`는 항목이 최대 개수를 초과하면 가장 오래된 항목을 자동으로 제거한다. 별도로 크기를 체크하거나 오래된 항목을 직접 삭제하는 코드가 필요 없다.

일반 리스트를 쓰면:

```python
_store.append(entry)
if len(_store) > 100:
    _store.pop(0)  # 직접 제거 코드 필요
```

`deque(maxlen=100)`을 쓰면:

```python
_store.append(entry)  # 이것만으로 충분
```

또 `deque`에서 `list()`를 사용해 최신순 정렬도 간단하다.

```python
recent = list(_store)
recent.reverse()  # append 순서의 역방향 = 최신순
return recent[:limit]
```

---

## 4. 히스토리를 어느 계층에서 기록하는가

히스토리 기록 위치를 두 곳으로 나눴다.

**`agent_runner.py`**: 비동기 Job (`POST /agent/jobs`)이 완료됐을 때 기록한다. 성공/실패 여부와 관계없이 모든 결과를 기록한다.

**`agent.py` 라우터**: 즉시 실행 API (`POST /agent/plan`)가 완료됐을 때 기록한다. 성공 시와 실패 시 각각 기록한다.

서비스 계층(`llm_client.py`)이 아니라 그 위 계층에서 기록하는 이유는, `generate_agent_plan()` 함수 자체는 "LLM을 호출해서 결과를 반환"하는 역할만 해야 하기 때문이다. 히스토리를 저장하는 것은 별개의 관심사다. 이렇게 하면 나중에 히스토리 저장 방식을 바꿀 때 LLM 호출 코드를 건드리지 않아도 된다.

---

## 5. `GET /history`의 `limit` 쿼리 파라미터

```python
@router.get("")
def get_history(
    limit: int = Query(default=20, ge=1, le=100, description="반환할 최대 항목 수 (1~100)"),
):
```

FastAPI의 `Query(ge=1, le=100)`은 값 검증을 자동으로 처리한다. `limit`이 1 미만이거나 100 초과이면 FastAPI가 자동으로 422 Unprocessable Entity를 반환한다. 코드에서 직접 범위를 체크할 필요가 없다.

---

## 6. `HistoryEntry.created_at`과 `completed_at`을 분리한 이유

비동기 Job의 경우:
- `created_at` = Job이 접수된 시각 (POST /agent/jobs 호출 시각)
- `completed_at` = LLM 실행이 완료된 시각

이 두 값이 다를 수 있다. LLM 응답에 10초가 걸렸다면 두 값의 차이가 10초다. 이 차이를 기록해두면 나중에 "LLM 응답 시간이 얼마나 걸렸는지"를 계산할 수 있다.

즉시 실행 API(`/agent/plan`)는 동기 방식이라 두 값이 거의 같다.

---

## 7. 보안 주의사항 — 왜 히스토리에 주의해야 하는가

히스토리에는 `user_request`가 포함된다. 사용자가 이 필드에 실수로 다음과 같은 내용을 넣을 수 있다.

- API Key: "OPENAI_API_KEY=sk-abc123인데..."
- 개인정보: 이름, 이메일, 전화번호
- 내부 시스템 정보: 서버 IP, DB 접속 정보

현재는 서버 메모리에만 저장되어서 서버 재시작 시 사라지지만, 나중에 DB나 로그 시스템으로 연동하면 영구 저장될 수 있다. 그때는 다음을 고려해야 한다.

- **저장 전 민감정보 탐지 및 마스킹**
- **접근 제어**: `GET /history`에 인증 미들웨어 추가
- **저장 기간 제한**: 일정 기간 후 자동 삭제 정책

---

## 8. 이번 단계 핵심 포인트

| 개념 | 핵심 내용 |
|------|----------|
| 요약 저장 | 전체 결과 대신 goal, step_count 등 핵심 필드만 저장 |
| `deque(maxlen=N)` | 크기 제한이 있는 FIFO 큐, 직접 크기 관리 불필요 |
| 히스토리 기록 위치 | 라우터/runner 계층에서 기록, LLM 서비스와 관심사 분리 |
| `Query(ge=, le=)` | FastAPI가 쿼리 파라미터 범위를 자동 검증 |
| 보안 관점 | `user_request` 필드에 민감정보 포함 가능성, DB 저장 시 주의 필요 |

---

## 9. 다음 단계에서 할 것

- 히스토리 항목 단건 삭제 (`DELETE /history/{entry_id}`)
- 히스토리 전체 초기화 (`DELETE /history`)
- 상태 필터링 (`GET /history?status=failed`)
- 인증 미들웨어 추가로 히스토리 접근 보호
