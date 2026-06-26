"""
Redis List 기반 단기 메모리 큐.

PostgreSQL History(장기 이력)와 달리, 이 모듈은 Agent가 최근 작업 흐름을
참고할 수 있도록 최근 N개의 이벤트를 Redis에 순서대로 보관한다.

TTL을 설정하지 않아도 LTRIM으로 크기를 제한하기 때문에 Redis 메모리를 무한히 사용하지 않는다.
"""
import json
from datetime import datetime, timezone
from typing import Any

from redis import Redis

from app.core.config import settings

# Redis.from_url(): Step 08의 task_queue.py와 같은 패턴. 연결은 lazy(지연)로 맺어진다.
_redis = Redis.from_url(settings.redis_url)

# Redis에서 이 키 이름의 List에 이벤트가 순서대로 쌓인다.
MEMORY_KEY = "agent:memory"

# 이벤트 타입 상수 — 문자열 리터럴로 정의해서 오타를 방지한다.
EVENT_JOB_CREATED = "job_created"
EVENT_JOB_RUNNING = "job_running"
EVENT_JOB_SUCCEEDED = "job_succeeded"
EVENT_JOB_FAILED = "job_failed"
EVENT_PLAN_GENERATED = "plan_generated"
EVENT_PLAN_FAILED = "plan_failed"


def push_event(
    event_type: str,
    payload: dict[str, Any],
    job_id: str | None = None,
) -> None:
    """
    이벤트를 Redis 메모리 큐의 앞(왼쪽)에 삽입한다.
    최대 크기를 초과하면 오래된 이벤트를 자동으로 제거한다.
    Redis 연결 실패는 조용히 무시한다 — 메인 흐름에 영향을 주지 않는다.
    """
    try:
        event = {
            "event_type": event_type,
            "job_id": job_id,
            "payload": payload,
            # isoformat(): datetime을 ISO 8601 문자열로 변환 ("2026-06-25T12:00:00+00:00")
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        # LPUSH: 리스트 왼쪽(앞)에 삽입 → 최신 이벤트가 항상 index 0에 위치
        # ensure_ascii=False: 한글 등 비ASCII 문자를 그대로 저장 (이스케이프하지 않음)
        _redis.lpush(MEMORY_KEY, json.dumps(event, ensure_ascii=False))
        # LTRIM: 리스트를 0번부터 (max-1)번까지만 남기고 나머지를 삭제
        # → 최대 memory_max_size 개의 이벤트만 유지됨
        _redis.ltrim(MEMORY_KEY, 0, settings.memory_max_size - 1)
    except Exception:
        # 메모리 큐는 선택적 기능 — Redis가 없거나 오류가 나도 Agent Job은 계속 진행
        pass


def get_recent(limit: int = 20) -> list[dict]:
    """
    최근 이벤트를 최신 순으로 반환한다.
    Redis 연결 실패 시 빈 리스트를 반환한다.
    """
    try:
        # LRANGE: 리스트의 [start, stop] 인덱스 범위 조회 (양 끝 포함)
        # index 0이 가장 최신 이벤트 (LPUSH로 넣었기 때문)
        raw_items = _redis.lrange(MEMORY_KEY, 0, limit - 1)
        # 각 항목은 bytes 타입 → json.loads로 dict로 역직렬화
        return [json.loads(item) for item in raw_items]
    except Exception:
        return []
