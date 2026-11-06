# -*- coding: utf-8 -*-
"""事件对接（EV）与幂等处理。

依据《广场接入说明》第 7 章「事件对接（EV）」：

  事件         方向          载荷要点
  EV-04 项目验收通过   工坊 → 广场    projectId、teamId、验收状态、评分、评语
  EV-05 作品发布       广场 → 底座    workId、projectId、authorUid、memberUids、visibility
  EV-06 作品转课例     广场 → 自学平台 workId、operatorUid、purpose、targetCourseId

关键要求：
  - 事件消费必须按 eventId 去重（幂等）；
  - 消费失败进重试队列（指数退避，最多 5 次）并告警，不允许静默丢弃；
  - 事件签名由对应 AppKey 承担（Q-G4 待确认口径）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from . import sign as _sign
from .contracts import EventEnvelope

MAX_RETRY = 5


class IdempotentStore:
    """eventId 幂等去重存储（生产用 Redis SETNX，本地用内存）。"""

    def seen(self, event_id: str) -> bool:
        raise NotImplementedError

    def mark(self, event_id: str) -> None:
        raise NotImplementedError


class MemoryIdempotentStore(IdempotentStore):
    def __init__(self):
        self._ids: set[str] = set()

    def seen(self, event_id: str) -> bool:
        return event_id in self._ids

    def mark(self, event_id: str) -> None:
        self._ids.add(event_id)


def retry_backoff(attempt: int) -> float:
    """指数退避：2^attempt 秒，attempt 从 0 起。"""
    return min(2.0 ** attempt, 60.0)


@dataclass
class ConsumeResult:
    consumed: bool      # True=本次实际处理；False=重复事件被去重跳过
    attempts: int       # 实际重试次数（0 表示首次成功）


def consume_event(envelope: EventEnvelope, store: IdempotentStore,
                  handler, max_retry: int = MAX_RETRY) -> ConsumeResult:
    """消费一个事件：eventId 去重 + 指数退避重试（最多 5 次）。

    参数：
      envelope  事件信封
      store     eventId 去重存储
      handler   业务处理函数 callable(envelope) -> None，抛异常视为失败
    返回：
      ConsumeResult(consumed, attempts)
    """
    if store.seen(envelope.event_id):
        return ConsumeResult(consumed=False, attempts=0)

    last_err: Exception | None = None
    for attempt in range(max_retry + 1):
        try:
            handler(envelope)
            store.mark(envelope.event_id)
            return ConsumeResult(consumed=True, attempts=attempt)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retry:
                time.sleep(retry_backoff(attempt))

    # 重试耗尽仍失败：不允许静默丢弃，必须告警（这里抛出让上层落告警/死信队列）。
    raise EventConsumeFailed(envelope.event_id, last_err)


class EventConsumeFailed(Exception):
    def __init__(self, event_id: str, cause: Exception | None):
        self.event_id = event_id
        self.cause = cause
        super().__init__("事件消费失败 eventId=%s: %s" % (event_id, cause))


def sign_event(app_key: str, app_secret: str, envelope: EventEnvelope) -> dict:
    """事件发送方：对事件载荷做 L2 签名（返回附加到请求的签名头）。

    事件体为信封 JSON（保证序列化完成后签名，签名后不再改动）。
    """
    body = json.dumps({
        "eventId": envelope.event_id,
        "eventType": envelope.event_type,
        "timestamp": envelope.timestamp,
        "source": envelope.source,
        "payload": envelope.payload,
    }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # 事件签名走 L2（Q-G4：具体由哪个 AppKey 承担待总平台确认）。
    return _sign.build_signature(app_key, app_secret, "POST", "/events", "",
                                 body)
