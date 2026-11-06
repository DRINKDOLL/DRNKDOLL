# -*- coding: utf-8 -*-
"""广场网关接入交叉验收脚本（35 条断言，对照《统一身份与网关接入说明文档》）。

覆盖三大要素（对齐接入结论的验收口径）：
  要素 1  入站：网关 → 广场（严格验签，伪造请求 403）
           - 服务态 L2 签名：缺头/错密钥/未知 AppKey/算法非法/时间戳超窗/nonce 重放
           - 用户态身份头：缺 X-Internal-Sign → 403/40303、伪造 → 403/40303、
             越权 → 403/70002、令牌过期 → 401/40103
           - 功能联动闭环：注入方 identity_injector → 校验方端到端（作者 200 /
             越权 403-70002 / 未签名 403-40303 / 两侧签名串一致）
  要素 2  出站：广场 → 网关（L2 签名，账号确认 confirmed）
           - 本地桩校验出站签名串正确，且正向/反向结论解析正确
  要素 3  上游切换：桩 → 真实 BFF（由统一身份登录链路承担，另见 verify_unified_login.js）

内部签名密钥与 server.py 走同一解析（env > configs/secrets.json > 演示兜底）。

用法：
    python scripts/verify_gateway.py                     # 默认 http://127.0.0.1:8094
    python scripts/verify_gateway.py --base http://127.0.0.1:8094
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway import sign as gwsign  # noqa: E402
from gateway import identity as gwid  # noqa: E402
from gateway.config import (  # noqa: E402
    internal_sign_secret_source,
    resolve_internal_sign_secret,
)
from gateway.contracts import AcceptanceResult, BadgeState  # noqa: E402
from gateway.if07 import derive_badge  # noqa: E402
from gateway.identity_injector import build_identity_headers, call_user_api  # noqa: E402

FAILS = []
TOTAL = 0

# 用户态内部签名密钥：与 server.py 走同一解析（env > secrets.json > 演示兜底），
# 保证「注入方」与「校验方」密钥一致——这是联动能触发的前提。
INTERNAL_SIGN_SECRET = resolve_internal_sign_secret(allow_demo=True)
# 出站账号确认桩使用的广场 AppSecret（仅本脚本联调用）。
PLAZA_SECRET = "plaza-secret-demo"


def check(cond: bool, name: str, extra: str = "") -> None:
    global TOTAL
    TOTAL += 1
    print(("%2d [PASS] " % TOTAL if cond else "%2d [FAIL] " % TOTAL) + name
          + ((" -> " + extra) if extra else ""))
    if not cond:
        FAILS.append(name)


def call(base: str, path: str, app_key: str = "", secret: str = "",
         nonce: str | None = None, ts: int | None = None, signed: bool = True,
         alg: str | None = None, headers_extra: dict | None = None):
    """按 L2 规则签名并发起 GET。path 可带 query，函数内部拆开分别参与签名。"""
    headers = {}
    if signed:
        pure_path, _, query = path.partition("?")
        headers = gwsign.build_signature(
            app_key, secret, "GET", pure_path, query, b"",
            timestamp=ts, nonce=nonce,
        )
        if alg is not None:
            headers["X-Sign-Alg"] = alg
    if headers_extra:
        headers.update(headers_extra)
    req = urllib.request.Request(base + path, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=8) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def call_user(base: str, path: str, *, user_id: str, role: str = "student",
              client_id: str = "c1", token_exp: int | None = None,
              request_id: str = "req-u1", auth_mode: str = "user",
              sign: bool = True, tamper: bool = False):
    """按用户态规则构造网关注入身份头（含 X-Internal-Sign）并发起 GET。"""
    exp = token_exp if token_exp is not None else int(time.time()) + 600
    hdrs = {
        "X-User-Id": user_id,
        "X-User-Role": role,
        "X-Client-Id": client_id,
        "X-Token-Exp": str(exp),
        "X-Request-Id": request_id,
        "X-Auth-Mode": auth_mode,
    }
    if sign:
        hdrs["X-Internal-Sign"] = gwid._internal_sign_value(hdrs, INTERNAL_SIGN_SECRET)
        if tamper:
            # 伪造：篡改签名值
            hdrs["X-Internal-Sign"] = "0" * len(hdrs["X-Internal-Sign"])
    req = urllib.request.Request(base + path, method="GET")
    for k, v in hdrs.items():
        req.add_header(k, v)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=8) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


# ---------------------------------------------------------------------------
# 出站账号确认本地桩：模拟论坛网关 POST /answer/api/v1/account/verify
# ---------------------------------------------------------------------------
class _VerifyStubHandler(BaseHTTPRequestHandler):
    server_version = "VerifyStub/1.0"
    secret = PLAZA_SECRET

    def log_message(self, fmt, *args):  # 静默
        pass

    def _json(self, status: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/answer/api/v1/account/verify":
            self._json(404, {"code": 40400, "message": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length)
        headers = {k: self.headers.get(k, "") for k in
                   ("X-App-Key", "X-Timestamp", "X-Nonce", "X-Sign-Alg", "X-Signature")}
        # 校验出站签名串（证明客户端 L2 签名构造正确）
        canonical = gwsign.build_canonical(
            headers["X-App-Key"], headers["X-Timestamp"], headers["X-Nonce"],
            "POST", path, "", body)
        expected = gwsign.sign(self.secret, canonical)
        if not hmac.compare_digest(expected, headers["X-Signature"]):
            self._json(401, {"code": 40105, "message": "L2 签名校验失败",
                             "data": None, "requestId": "stub"})
            return
        try:
            data = json.loads(body.decode("utf-8"))
        except ValueError:
            self._json(400, {"code": 40001, "message": "bad body", "data": None})
            return
        if data.get("login") == "admin" and data.get("pass") == "Admin@12345":
            self._json(200, {"code": 0, "message": "ok", "data": {
                "confirmed": True, "user_id": "1", "username": "admin",
                "display_name": "管理员", "role": "admin",
                "e_mail_masked": "a***@jspi.edu.cn", "account_source": "forum",
                "status": "active", "request_id": "req-1"}})
        else:
            self._json(401, {"code": 40104, "message": "账号或密码错误", "data": {
                "confirmed": False, "reason": "invalid_credentials"},
                "requestId": "stub"})


def _start_verify_stub() -> tuple[ThreadingHTTPServer, str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _VerifyStubHandler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, "http://127.0.0.1:%d" % port


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8094")
    ap.add_argument("--forum-secret", default="forum-secret-demo")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    sec = args.forum_secret
    works = "/api/v1/internal/works"

    # ==================== 要素 1 · 服务态 L2 签名 ====================
    st, body = call(base, works, signed=False)
    check(st == 401 and body.get("code") == "40105", "服务态·无签名头被拒（401/40105）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, works, "svc-forum", "wrong-secret")
    check(st == 401 and body.get("code") == "40105", "服务态·密钥错误签名不匹配（401/40105）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, works, "svc-unknown", "whatever")
    check(st == 401 and body.get("code") == "40108", "服务态·未知 AppKey（401/40108）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, works, "svc-forum", sec, alg="MD5")
    check(st == 401 and body.get("code") == "40105", "服务态·签名算法非法（401/40105）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, works, "svc-forum", sec, ts=int(time.time()) - 1000)
    check(st == 401 and body.get("code") == "40106", "服务态·时间戳过旧超窗（401/40106）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, works, "svc-forum", sec, ts=int(time.time()) + 1000)
    check(st == 401 and body.get("code") == "40106", "服务态·时间戳超前超窗（401/40106）",
          "%s %s" % (st, body.get("code")))

    # nonce 需每次运行唯一：服务端 nonce 表跨脚本运行保留，用固定值会在复跑时
    # 首次调用即被判为重放（测试不可重复）。用进程内唯一串保证可复跑。
    uniq_nonce = "verify-nonce-%d" % time.time_ns()
    st1, _ = call(base, works, "svc-forum", sec, nonce=uniq_nonce)
    st2, b2 = call(base, works, "svc-forum", sec, nonce=uniq_nonce)
    check(st1 == 200 and st2 == 401 and b2.get("code") == "40107",
          "服务态·nonce 重放被拒（首次 200 / 重放 401/40107）",
          "%s / %s %s" % (st1, st2, b2.get("code")))

    # ---- 路由白名单（默认拒绝）----
    st, body = call(base, "/api/v1/internal/lab/acceptance/prj-001", "svc-study", "study-secret-demo")
    check(st == 403 and body.get("code") == "70007", "服务态·越权路由被拒（svc-study→lab，403/70007）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, "/api/v1/internal/lab/acceptance/prj-001", "svc-lab", "lab-secret-demo")
    check(st == 200 and body.get("projectId") == "prj-001", "服务态·svc-lab 授权路径可访问（200）", str(st))

    st, body = call(base, "/api/v1/internal/works?page=1&size=20", "svc-forum", sec)
    ok_list = st == 200 and body.get("total", 0) >= 2 and len(body.get("items", [])) >= 2
    check(ok_list, "服务态·列表正常返回（200 且 total≥2）", "%s total=%s" % (st, body.get("total")))
    first_id = (body.get("items") or [{}])[0].get("workId", "")

    st, body = call(base, "/api/v1/internal/works/%s" % first_id, "svc-forum", sec)
    check(st == 200 and body.get("workId") == first_id, "服务态·详情正常返回（200）", str(st))

    st, body = call(base, "/api/v1/internal/works/work-9999", "svc-forum", sec)
    check(st == 404 and body.get("code") == "70005", "服务态·作品不存在（404/70005）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, "/api/v1/internal/works?page=0&size=20", "svc-forum", sec)
    check(st == 400 and body.get("code") == "70001", "服务态·分页 page=0 校验（400/70001）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, "/api/v1/internal/works?page=1&size=101", "svc-forum", sec)
    check(st == 400 and body.get("code") == "70001", "服务态·分页 size=101 上限校验（400/70001）",
          "%s %s" % (st, body.get("code")))

    st, body = call(base, "/api/v1/internal/works/by-project/prj-001", "svc-forum", sec)
    check(st == 200 and body.get("projectId") == "prj-001", "服务态·按项目查投稿（200）", str(st))

    st, body = call(base, "/api/v1/internal/works/by-team/team-01", "svc-forum", sec)
    check(st == 200 and "items" in body, "服务态·按团队查作品（200）", str(st))

    st, body = call(base, "/api/v1/internal/teams/10231", "svc-forum", sec)
    check(st == 200 and body.get("teamId") == "team-01", "服务态·用户团队归属（200）", str(st))

    # ==================== 要素 1 · 用户态入站身份 ====================
    u_work = "/api/v1/user/works/work-1001"

    st, body = call_user(base, u_work, user_id="10231", sign=False)
    check(st == 403 and body.get("code") == "40303", "用户态·缺 X-Internal-Sign → 403/40303",
          "%s %s" % (st, body.get("code")))

    st, body = call_user(base, u_work, user_id="10231", sign=True, tamper=True)
    check(st == 403 and body.get("code") == "40303", "用户态·伪造 X-Internal-Sign → 403/40303",
          "%s %s" % (st, body.get("code")))

    st, body = call_user(base, u_work, user_id="10231", role="student")
    check(st == 200 and body.get("workId") == "work-1001", "用户态·本人访问自己作品（200）", str(st))

    st, body = call_user(base, u_work, user_id="99999", role="student")
    check(st == 403 and body.get("code") == "70002", "用户态·水平越权被拒（403/70002）",
          "%s %s" % (st, body.get("code")))

    st, body = call_user(base, u_work, user_id="99999", role="admin")
    check(st == 200 and body.get("workId") == "work-1001", "用户态·管理员越权豁免（200）", str(st))

    st, body = call_user(base, u_work, user_id="10231", token_exp=int(time.time()) - 10)
    check(st == 401 and body.get("code") == "40103", "用户态·令牌过期 → 401/40103",
          "%s %s" % (st, body.get("code")))

    st, body = call_user(base, "/api/v1/user/works/work-9999", user_id="10231")
    check(st == 404 and body.get("code") == "70005", "用户态·作品不存在（404/70005）",
          "%s %s" % (st, body.get("code")))

    # ============ 功能联动闭环（注入方 → 校验方 端到端）============
    # 用网关侧注入器（identity_injector）构造身份头，走真实链路触发联动。
    # 注意：注入器与此处共用同一密钥解析，故本条同时验证「两侧密钥一致」。
    print("    · 内部签名密钥来源：%s" % internal_sign_secret_source())
    st, body = call_user_api("/api/v1/user/works/work-1001", user_id="10231",
                             role="student", base=base)
    check(st == 200 and body.get("workId") == "work-1001",
          "联动·注入身份头触发链路（作者本人 200）", str(st))

    # 联动反向：注入他人身份 → 校验方拦下水平越权。
    st, body = call_user_api("/api/v1/user/works/work-1001", user_id="88888",
                             role="student", base=base)
    check(st == 403 and body.get("code") == "70002",
          "联动·越权触发被拦（非作者 403/70002）", "%s %s" % (st, body.get("code")))

    # 联动安全：注入头缺签名 → 校验方判为绕过网关直连。
    bad = {"X-User-Id": "10231", "X-User-Role": "student",
           "X-Client-Id": "c1", "X-Token-Exp": str(int(time.time()) + 600),
           "X-Request-Id": "req-x", "X-Auth-Mode": "user"}
    req = urllib.request.Request(base + "/api/v1/user/works/work-1001", method="GET")
    for k, v in bad.items():
        req.add_header(k, v)
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=8) as r:
            st, body = r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        st, body = e.code, json.loads(e.read().decode("utf-8", "ignore"))
    check(st == 403 and body.get("code") == "40303",
          "联动·未注入签名被拒（403/40303）", "%s %s" % (st, body.get("code")))

    # 联动触发方复用性：注入器生成的头必须与校验方规范化串完全一致。
    hdr = build_identity_headers("10231", "student", secret=INTERNAL_SIGN_SECRET)
    expect_sign = gwid._internal_sign_value(hdr, INTERNAL_SIGN_SECRET)
    check(hdr.get("X-Internal-Sign") == expect_sign,
          "联动·注入器与校验方签名串一致", "")

    # ==================== 预留 lab 接口 ====================
    st, body = call(base, "/api/v1/internal/lab/badges/work-1001", "svc-lab", "lab-secret-demo")
    check(st == 200 and body.get("workId") == "work-1001", "预留·徽章查询（svc-lab 200）", str(st))

    st, body = call(base, "/api/v1/internal/lab/acceptance/prj-002", "svc-lab", "lab-secret-demo")
    check(st == 200 and body.get("projectId") == "prj-002", "预留·验收结论查询（svc-lab 200）", str(st))

    # ==================== 签名工具纯函数 ====================
    cq = gwsign.canonical_query("b=2&a=1&a=0")
    check(cq == "a=1&a=0&b=2", "工具·canonical_query 按 key 排序且稳定", cq)

    empty_hash = gwsign.build_canonical("k", "100", "n", "get", "/p", "", b"")
    import hashlib
    expect = "\n".join(["k", "100", "n", "GET", "/p", "",
                        hashlib.sha256(b"").hexdigest()])
    check(empty_hash == expect, "工具·GET 空 body 规范化串正确", "")

    # ==================== IF-07 降级派生（三分支）====================
    b1 = derive_badge("work-1", AcceptanceResult(
        project_id="prj-1", team_id="team-01", accepted=True, score=92.5,
        comment="", verified_at="2026-11-01T10:00:00+08:00"))
    b2 = derive_badge("work-1", None, BadgeState(work_id="work-1", certified=True,
                                                 verified_at="2026-11-01", pending_check=False))
    b3 = derive_badge("work-2", None, None)
    ok07 = (b1.certified is True and b1.pending_check is False
            and b2.certified is True and b2.pending_check is True
            and b3.certified is False and b3.pending_check is False)
    check(ok07, "IF-07 降级三分支（正常认证 / 不可用沿用待核验 / 无历史不认证）",
          "%s/%s/%s" % (b1.certified, b2.pending_check, b3.certified))

    # ==================== 要素 2 · 出站账号确认（本地桩）====================
    from gateway.account_verify import verify_account
    httpd, stub_base = _start_verify_stub()
    try:
        r_ok = verify_account("admin", "Admin@12345", app_key="jy-plaza-svc",
                              app_secret=PLAZA_SECRET, base=stub_base, timeout=5)
        check(r_ok.confirmed is True and r_ok.user_id == "1" and r_ok.role == "admin",
              "出站·账号确认正向（签名通过 + confirmed=True）",
              "http=%s uid=%s role=%s" % (r_ok.http_status, r_ok.user_id, r_ok.role))

        r_bad = verify_account("admin", "wrong-pass", app_key="jy-plaza-svc",
                               app_secret=PLAZA_SECRET, base=stub_base, timeout=5)
        check(r_bad.confirmed is False and r_bad.code == 40104,
              "出站·账号确认失败防枚举（confirmed=False / 40104）",
              "http=%s code=%s reason=%s" % (r_bad.http_status, r_bad.code, r_bad.reason))
    finally:
        httpd.shutdown()

    print("\n=== 共 %d 条 | %s ===" % (
        TOTAL, "全部通过" if not FAILS else "失败 %d 项: %s" % (len(FAILS), FAILS)))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
