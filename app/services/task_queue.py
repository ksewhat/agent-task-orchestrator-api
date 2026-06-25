from redis import Redis
from rq import Queue

from app.core.config import settings

# Redis.from_url(): URL 문자열로 Redis 연결 객체 생성
# 실제 TCP 연결은 큐를 처음 사용할 때(lazy) 맺어지므로 서버 시작 시점에 Redis가 없어도 import는 가능하다.
_redis_conn = Redis.from_url(settings.redis_url)

# Queue: 작업(job)을 쌓아두는 RQ 큐
# name="agent" → Redis에서 "rq:queue:agent" 키로 관리됨
# RQ Worker는 이 이름을 보고 처리할 큐를 결정함
task_queue = Queue(name="agent", connection=_redis_conn)
