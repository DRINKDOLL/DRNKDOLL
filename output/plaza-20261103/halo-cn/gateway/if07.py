# -*- coding: utf-8 -*-
"""IF-07 消费方客户端：广场调用实训工坊获取作品验收结论。

依据《广场接入说明》2.2 / 2.3 / 6.3：
  - 广场作为「服务态调用方」，用 AppKey svc-plaza + L2 签名消费工坊 IF-07。
  - 返回的作品验收结论派生「认证徽章」（不可手动标注）。
  - IF-07 不可用时：已有徽章沿用上次校验结果并标「待核验」，新投稿暂不获徽章，
    但不阻断投稿主流程（《说明》6.3，广场需求文档 7.6）。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from . import sign as _sign
from .config import config, ENV_PLAZA_APP_KEY, ENV_PLAZA_APP_SECRET
from .contracts import AcceptanceResult, BadgeState


# 工坊 IF-07 基址（生产由配置下发，此处演示）。
LAB_BASE = os.environ.get("PLAZA_LAB_BASE", "http://127.0.0.1:8094")
IF07_PATH = "/api/v1/internal/lab/acceptance"


class If07Client:
    """广场消费实训工坊 IF-07 的客户端。

    用法：
        client = If07Client(app_key="svc-plaza", app_secret="...")
        result = client.get_acceptance(project_id="prj-001")   # -> AcceptanceResult
    """

    def __init__(self, app_key: str | None = None, app_secret: str | None = None,
                 base: str | None = None):
        self.app_key = app_key or os.environ.get(ENV_PLAZA_APP_KEY, "svc-plaza")
        self.app_secret = app_secret or os.environ.get(ENV_PLAZA_APP_SECRET, "plaza-secret-demo")
        self.base = (base or LAB_BASE).rstrip("/")

    def get_acceptance(self, project_id: str, timeout: int = 5) -> AcceptanceResult:
        """按 projectId 查询验收结论。

        失败（网络/签名/工坊不可用）抛出 If07Unavailable，由调用方按 6.3 降级。
        """
        path = "%s/%s" % (IF07_PATH, project_id)
        headers = _sign.build_signature(
            self.app_key, self.app_secret, "GET", path, "", b""
        )
        req = urllib.request.Request(self.base + path, method="GET")
        for k, v in headers.items():
            req.add_header(k, v)
        req.add_header("Accept", "application/json")
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
                TimeoutError) as exc:
            raise If07Unavailable(str(exc)) from exc

        return AcceptanceResult(
            project_id=data.get("projectId", project_id),
            team_id=data.get("teamId", ""),
            accepted=bool(data.get("accepted", False)),
            score=data.get("score"),
            comment=data.get("comment", ""),
            verified_at=data.get("verifiedAt", ""),
        )


class If07Unavailable(Exception):
    """IF-07 不可用（网络/工坊故障/签名失败），触发降级。"""


def derive_badge(work_id: str, result: AcceptanceResult | None,
                 last: BadgeState | None = None) -> BadgeState:
    """由验收结论派生认证徽章状态，并实现 6.3 降级策略。

    返回 BadgeState：
      - result 正常：certified = result.accepted，verified_at = result.verified_at，
        pending_check = False。
      - result 为 None（IF-07 不可用）：
          * 有上次结果 last → 沿用 last 并标 pending_check = True（待核验）；
          * 无上次结果 → certified = False（新投稿暂不获徽章），pending_check = False，
            但不阻断投稿。
    """
    if result is not None:
        return BadgeState(work_id=work_id, certified=result.accepted,
                          verified_at=result.verified_at or None, pending_check=False)
    if last is not None:
        return BadgeState(work_id=work_id, certified=last.certified,
                          verified_at=last.verified_at, pending_check=True)
    return BadgeState(work_id=work_id, certified=False,
                      verified_at=None, pending_check=False)
