# -*- coding: utf-8 -*-
"""IF-08 / 预留接口的 HTTP 服务端实现（可运行桩）。

依据《广场接入说明》4.4 第（四）组「服务态路由」实现广场作为「服务态提供方」
对外暴露的只读接口。所有接口统一：
  - L2 签名校验（X-App-Key + HMAC-SHA256）
  - 默认拒绝：未声明策略的路由一律 404/403
  - 只读、限流（IF-08 100 QPS）
  - 不返回草稿/待审/已下架/受限作品

本桩用于联调/验收演示，数据源为内存示例；生产环境将 `DATA_PROVIDER` 替换为
Halo 内容接口（/apis/api.content.halo.run/v1alpha1/posts 及扩展元数据）即可。

启动：
    python -m gateway.server [--port 8094]
"""
from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import sign as _sign
from .errors import biz, biz_http, BizError
from .contracts import PageQuery
from .config import (
    ENV_INTERNAL_SIGN_SECRET,
    internal_sign_secret_source,
    resolve_internal_sign_secret,
)
from .identity import (
    Identity,
    InternalSignError,
    ROLE_ADMIN,
    enforce_owner,
    parse_identity,
)

# 默认监听端口（独立于 Halo 8092 与成果管理代理 8093）。
PORT = int(os.environ.get("PLAZA_GW_PORT", "8094"))
HOST = os.environ.get("PLAZA_GW_HOST", "0.0.0.0")

# ---------------------------------------------------------------------------
# 用户态入站（经网关的浏览器/终端请求）
# ---------------------------------------------------------------------------
# 用户态请求不由消费方 AppKey 的 L2 签名进入，而是由**网关**在转发时注入可信
# 身份头（X-User-Id / X-User-Role / ... / X-Internal-Sign）。广场业务服务必须：
#   1) 校验 X-Internal-Sign，缺失或错误一律 403/40303（视为绕过网关直连）；
#   2) 校验 X-Token-Exp，过期一律 401/40103；
#   3) 做水平越权校验（不得仅凭 X-User-Id 放行）。
# 共享密钥仅服务端持有，生产必须经环境变量注入。
USER_MODE_PREFIX = "/api/v1/user/"
# 共享密钥仅服务端持有；解析顺序：环境变量 > configs/secrets.json > 演示兜底。
# 网关（注入方）与广场服务（校验方）必须解析到同一值，否则联动整体 403。
INTERNAL_SIGN_SECRET = resolve_internal_sign_secret(allow_demo=True)

# 服务态消费方 AppKey 台账（由广场侧分配并配置路由白名单，见《说明》5.1）。
# 生产环境从配置中心读取；此处为演示台账。
CONSUMER_APP_KEYS = {
    # appKey -> appSecret（仅服务端持有）
    "svc-forum":  os.environ.get("GW_FORUM_SECRET", "forum-secret-demo"),
    "svc-study":  os.environ.get("GW_STUDY_SECRET", "study-secret-demo"),
    "svc-lab":    os.environ.get("GW_LAB_SECRET", "lab-secret-demo"),
    # 广场自身（本服务同时扮演「实训工坊」时，广场作为消费方来访工坊接口用此身份；
    # 仅放行 lab 路径，不授予 works 权限）。
    "svc-plaza":  os.environ.get("GW_PLAZA_SECRET", "plaza-secret-demo"),
}

# 路由白名单：appKey -> 允许访问的路径（默认拒绝原则）。
# 使用精确的路径段匹配，避免「前缀 /api/v1/internal/ 放行全部」这类过宽授权。
# 每条为「完整路径」或「以 / 结尾的路径前缀（作用于该目录下全部子路径）」。
ROUTE_WHITELIST = {
    "svc-forum": [
        "/api/v1/internal/works",            # IF-08 列表
        "/api/v1/internal/works/",           # IF-08 详情/按项目/按团队
        "/api/v1/internal/teams/",           # IF-09 团队归属
    ],
    "svc-study": [
        "/api/v1/internal/works/",           # IF-08 详情
    ],
    "svc-lab": [
        "/api/v1/internal/works/",           # IF-08 详情
        "/api/v1/internal/lab/",             # 预留：实训工坊验收/徽章
    ],
    # 广场作为消费方：仅工坊侧接口，不含 works（最小授权）。
    "svc-plaza": [
        "/api/v1/internal/lab/",
    ],
}

# 简单令牌桶限流（单机演示；生产用 Redis 令牌桶按 AppKey 维度限 100 QPS）。
import time as _time

# 验签器必须是**进程级单例**：nonce 去重状态保存在验签器持有的 NonceStore 里，
# 若按请求新建验签器，每次都是一个空的 nonce 表，重放请求永远不会被拦住。
_APP_KEY_STORE = _sign.DictAppKeyStore(CONSUMER_APP_KEYS)
_NONCE_STORE = _sign.MemoryNonceStore()
_VERIFIER = _sign.SignatureVerifier(_APP_KEY_STORE, _NONCE_STORE)


class RateLimiter:
    """令牌桶限流（按 AppKey 维度，桶容量与补充速率均为 qps）。

    说明：此前实现是「固定最小间隔」（1/qps 秒内只放行一次），会把同一页面的
    并发调用（毫秒级连发数个请求）整批误判为超限而 429。令牌桶允许容量范围内的
    突发——只要桶内还有令牌即放行，长期平均速率仍被限制在 qps 以内。
    对应配置 plaza.if08.rate（默认 100 QPS）。
    """

    def __init__(self, qps: int = 100):
        self._qps = qps
        self._capacity = float(qps) if qps > 0 else 0.0
        self._state: dict[str, list] = {}  # key -> [tokens, last_ts]

    def allow(self, key: str) -> bool:
        if self._capacity <= 0:
            return True
        now = _time.time()
        tokens, last = self._state.get(key, (self._capacity, now))
        tokens = min(self._capacity, tokens + (now - last) * self._qps)
        if tokens >= 1.0:
            self._state[key] = [tokens - 1.0, now]
            return True
        self._state[key] = [tokens, now]
        return False


_rate = RateLimiter(int(os.environ.get("PLAZA_IF08_RATE", "100")))


class DataProvider:
    """数据源抽象。演示返回内存示例，生产替换为 Halo 内容查询。"""

    def list_works(self, page: int, size: int, uid: str | None = None,
                   team_id: str | None = None, project_id: str | None = None) -> dict:
        # 演示：返回 2 条公开作品（不含草稿/待审/下架/受限）。
        items = [
            {
                "workId": "work-1001", "title": "卡口车牌识别与轨迹还原",
                "coverUrl": "", "authorUid": uid or "10231",
                "projectId": project_id or "prj-001", "teamId": team_id or "team-01",
                "category": "交通管理", "tags": ["车牌识别", "轨迹拼接"],
                "likeCount": 18, "collectCount": 7,
                "reviewStatus": "passed", "certified": True,
                "publishTime": "2026-11-01T10:00:00+08:00", "visibility": "public",
            },
            {
                "workId": "work-1002", "title": "社区安防智能巡更系统",
                "coverUrl": "", "authorUid": uid or "10232",
                "projectId": project_id or "prj-002", "teamId": team_id or "team-02",
                "category": "治安管理", "tags": ["巡更", "安防"],
                "likeCount": 11, "collectCount": 3,
                "reviewStatus": "passed", "certified": False,
                "publishTime": "2026-11-02T14:30:00+08:00", "visibility": "public",
            },
        ]
        return {"page": page, "size": size, "total": len(items), "items": items}

    def get_work(self, work_id: str) -> dict | None:
        for it in self["list"]:
            if it["workId"] == work_id:
                d = dict(it)
                d["excerpt"] = "基于多路视频流的识别与还原方案"
                d["memberUids"] = [d["authorUid"]]
                return d
        return None

    def __getitem__(self, key: str):
        if key == "list":
            return self.list_works(1, 100)["items"]
        raise KeyError(key)


DATA = DataProvider()


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "PlazaGateway/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("[gw] %s %s\n" % (self.command, self.path))

    # ---- 通用响应 ----
    def _send(self, status: int, obj, headers: dict | None = None):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _send_ok(self, obj):
        self._send(200, obj)

    def _send_biz(self, code: str, request_id: str = ""):
        body = biz(code, request_id)
        self._send(biz_http(code), body)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        return self.rfile.read(length) if length > 0 else b""

    # ---- 请求分发 ----
    def _route(self):
        method = self.command
        path = self.path.split("?", 1)[0]
        query = self.path.split("?", 1)[1] if "?" in self.path else ""

        # 用户态入站：先于服务态分流（两者鉴权模型不同）。
        if path == USER_MODE_PREFIX.rstrip("/") or path.startswith(USER_MODE_PREFIX):
            return self._route_user_mode(method, path, query)

        # 只允许 GET（服务态只读）；其他方法默认拒绝。
        if method != "GET":
            self._send(405, {"error": "method not allowed"})
            return

        # 1) L2 签名校验（先验签名，再路由）。
        app_key = self._verify_signature(method, path, query)

        # 2) 路由白名单校验（默认拒绝）。
        if not self._in_whitelist(app_key, path):
            self._send(403, biz("70007", self._request_id()))
            return

        # 3) 限流。
        if not _rate.allow(app_key):
            self._send(429, {"code": "42901", "message": "触发限流",
                             "data": {"retryAfter": 1}, "requestId": self._request_id()})
            return

        # 4) 具体路由。
        m = re.fullmatch(r"/api/v1/internal/works", path)
        if m:
            return self._list_works(query)
        m = re.fullmatch(r"/api/v1/internal/works/([^/]+)", path)
        if m:
            return self._get_work(m.group(1))
        m = re.fullmatch(r"/api/v1/internal/works/by-project/([^/]+)", path)
        if m:
            return self._by_project(m.group(1))
        m = re.fullmatch(r"/api/v1/internal/works/by-team/([^/]+)", path)
        if m:
            return self._by_team(m.group(1))
        m = re.fullmatch(r"/api/v1/internal/teams/([^/]+)", path)
        if m:
            return self._team_of_user(m.group(1))

        # 预留：实训工坊后续对接接口（验收结果回写查询、徽章查询）。
        m = re.fullmatch(r"/api/v1/internal/lab/acceptance/([^/]+)", path)
        if m:
            return self._lab_acceptance(m.group(1))
        m = re.fullmatch(r"/api/v1/internal/lab/badges/([^/]+)", path)
        if m:
            return self._lab_badge(m.group(1))

        self._send(404, {"error": "not found"})

    def _request_id(self) -> str:
        return self.headers.get("X-Request-Id", "")

    # ---- 用户态入站：网关注入身份头 + X-Internal-Sign 校验 ----
    def _route_user_mode(self, method: str, path: str, query: str):
        """用户态请求：只读，必须经网关注入可信身份头。"""
        if method != "GET":
            self._send(405, {"error": "method not allowed"})
            return

        # 1) 解析并校验身份头（X-Internal-Sign 缺失/错误 → 403/40303）。
        identity = self._parse_identity()
        if identity is None:
            return  # 已回包

        # 2) 令牌有效期（X-Token-Exp 过期 → 401/40103）。
        if identity.token_exp is not None and identity.token_exp < int(_time.time()):
            self._send(401, {"code": "40103", "message": "令牌已过期",
                             "data": None, "requestId": identity.request_id})
            return

        # 3) 路由：GET /api/v1/user/works/{workId}（仅作者本人或管理员可见）。
        m = re.fullmatch(r"/api/v1/user/works/([^/]+)", path)
        if m:
            return self._user_get_work(m.group(1), identity)

        self._send(404, {"error": "not found"})

    def _parse_identity(self) -> "Identity | None":
        """从请求头解析网关注入身份。失败已回包，返回 None。"""
        headers = {
            "X-User-Id": self.headers.get("X-User-Id", ""),
            "X-User-Role": self.headers.get("X-User-Role", ""),
            "X-Client-Id": self.headers.get("X-Client-Id", ""),
            "X-Token-Exp": self.headers.get("X-Token-Exp", ""),
            "X-Request-Id": self.headers.get("X-Request-Id", ""),
            "X-Auth-Mode": self.headers.get("X-Auth-Mode", ""),
            "X-Internal-Sign": self.headers.get("X-Internal-Sign", ""),
        }
        try:
            return parse_identity(headers, INTERNAL_SIGN_SECRET,
                                  require_internal_sign=True)
        except InternalSignError as e:
            # 缺少/伪造 X-Internal-Sign：视为绕过网关直连，回 403/40303。
            self._send(403, {"code": "40303", "message": e.message,
                             "data": None, "requestId": self._request_id()})
            return None

    def _user_get_work(self, work_id: str, identity: "Identity"):
        """用户态作品查询：先鉴权（水平越权），再取数据。"""
        d = DATA.get_work(work_id)
        if d is None:
            self._send_biz("70005", identity.request_id)
            return
        # 水平越权：非作者且非管理员 → 403/70002。
        try:
            enforce_owner(identity, d.get("authorUid", ""))
        except BizError as e:
            self._send(e.http_status, biz(e.code, identity.request_id))
            return
        self._send_ok(d)

    def _verify_signature(self, method: str, path: str, query: str) -> str:
        headers = {
            "X-App-Key": self.headers.get("X-App-Key", ""),
            "X-Timestamp": self.headers.get("X-Timestamp", ""),
            "X-Nonce": self.headers.get("X-Nonce", ""),
            "X-Sign-Alg": self.headers.get("X-Sign-Alg", ""),
            "X-Signature": self.headers.get("X-Signature", ""),
        }
        body = self._read_body()
        try:
            return _VERIFIER.verify(headers, method, path, query, body)
        except _sign.SignatureError as e:
            # 网关错误码透传（40105/40106/40107/40108）
            self._send(401, {"code": e.code, "message": e.message,
                             "data": None, "requestId": self._request_id()})
            raise _AbortRouting()

    def _in_whitelist(self, app_key: str, path: str) -> bool:
        for entry in ROUTE_WHITELIST.get(app_key, []):
            if entry.endswith("/"):
                # 目录前缀：作用于该目录下全部子路径（含目录本身）。
                base = entry.rstrip("/")
                if path == base or path.startswith(entry):
                    return True
            else:
                # 精确路径。
                if path == entry:
                    return True
        return False

    # ---- 具体接口实现 ----
    def _list_works(self, query: str):
        from urllib.parse import parse_qs
        qs = parse_qs(query)
        page = int(qs.get("page", ["1"])[0])
        size = int(qs.get("size", ["20"])[0])
        pq = PageQuery(page, size)
        if pq.validate():
            self._send_biz("70001")
            return
        uid = qs.get("uid", [None])[0]
        team_id = qs.get("teamId", [None])[0]
        project_id = qs.get("projectId", [None])[0]
        self._send_ok(DATA.list_works(page, size, uid, team_id, project_id))

    def _get_work(self, work_id: str):
        d = DATA.get_work(work_id)
        if d is None:
            self._send_biz("70005")
            return
        self._send_ok(d)

    def _by_project(self, project_id: str):
        d = DATA.list_works(1, 100, project_id=project_id)
        self._send_ok({"projectId": project_id, "submitted": d["total"] > 0,
                       "works": d["items"]})

    def _by_team(self, team_id: str):
        d = DATA.list_works(1, 100, team_id=team_id)
        self._send_ok(d)

    def _team_of_user(self, uid: str):
        # IF-09（可选）：用户团队归属
        self._send_ok({"uid": uid, "teamId": "team-01"})

    def _lab_acceptance(self, project_id: str):
        # 预留：按 projectId 查工坊验收结论（广场消费 IF-07 的缓存结果）
        self._send_ok({"projectId": project_id, "accepted": True, "score": 92.5,
                       "comment": "", "verifiedAt": "2026-11-03T09:00:00+08:00"})

    def _lab_badge(self, work_id: str):
        # 预留：按 workId 查认证徽章
        self._send_ok({"workId": work_id, "certified": True,
                       "verifiedAt": "2026-11-03T09:00:00+08:00", "pendingCheck": False})

    # ---- HTTP 方法入口 ----
    def do_GET(self):
        try:
            self._route()
        except _AbortRouting:
            pass
        except BizError as e:
            self._send_biz(e.code, self._request_id())
        except Exception as e:  # noqa: BLE001
            self._send(500, {"code": "500", "message": "internal error",
                             "data": None, "requestId": self._request_id()})

    def do_POST(self):
        self.do_GET()

    def do_PUT(self):
        self.do_GET()


class _AbortRouting(Exception):
    """内部信号：签名校验失败已回包，中止后续路由。"""


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    print("广场网关接口服务已启动：http://%s:%d" % (HOST, PORT))
    print("IF-08 / 预留接口（L2 签名只读），消费方 AppKey：%s" % ", ".join(CONSUMER_APP_KEYS))
    src = internal_sign_secret_source()
    print("用户态联动 X-Internal-Sign 密钥来源：%s（%s）" % (
        src, "环境变量" if src == "env" else ("密钥文件" if src == "file" else "演示兜底，生产必须注入")))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
