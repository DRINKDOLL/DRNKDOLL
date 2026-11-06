# -*- coding: utf-8 -*-
"""统一身份登录 BFF 的 HTTP 端点（面向登录页前端）。

登录页前端通过本端点提交论坛账号密码，走统一身份登录完整链路：
    论坛账号确认 → Halo 本地用户映射/创建 → 角色映射。

成功后，前端引导用户凭同一凭据走 Halo 标准表单登录（POST /login）建立会话；
本端点不直接代建会话（避免绕过 Spring Security 的 CSRF/安全上下文），只做
「确认 + 映射 + 建本地用户」这前半段。

安全：
  - 密码仅在本进程请求处理期间短暂存在，不落盘、不写日志；
  - 失败统一返回同一结论，防账号枚举；
  - 只允许本机/可信来源调用（可选 Origin 校验）。

启动：
    python -m gateway.login_server [--port 8095]
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .unified_login import unified_login

PORT = int(os.environ.get("PLAZA_LOGIN_PORT", "8095"))
HOST = os.environ.get("PLAZA_LOGIN_HOST", "0.0.0.0")

# 允许的来源（登录页所在站点）。空列表表示不校验 Origin。
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "PLAZA_LOGIN_ORIGINS",
        "http://127.0.0.1:8092,http://localhost:8092",
    ).split(",") if o.strip()
]


class LoginHandler(BaseHTTPRequestHandler):
    server_version = "PlazaUnifiedLogin/1.0"

    # ---- 工具 ----
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _origin_allowed(self) -> bool:
        """Origin 校验：白名单命中，或与本次请求同主机（如局域网 IP 访问）。

        登录页与 BFF 同机部署、端口不同（8092 / 8095），因此「同 hostname、
        不同端口」视为可信来源；仅凭端口号无法区分站点，故不用端口比对。
        """
        origin = self.headers.get("Origin", "")
        if not origin:
            return True  # 非浏览器跨域场景（curl / 服务端调用）
        if origin in ALLOWED_ORIGINS:
            return True
        o = urlparse(origin)
        req_host = (self.headers.get("Host", "").split(":")[0] or "").strip()
        return bool(o.hostname) and bool(req_host) and o.hostname == req_host

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self):  # CORS 预检
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/unified-login":
            self.send_response(404)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # 可选 Origin 校验（防跨站盗用登录端点）
        if not self._origin_allowed():
            self._send_json(403, {"ok": False, "reason": "origin_denied"})
            return

        # 读取 JSON body（限定大小，防滥用）
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 4096:
                raise ValueError("bad length")
            raw = self.rfile.read(length).decode("utf-8")
            body = json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "reason": "bad_request"})
            return

        login = (body.get("username") or "").strip()
        password = body.get("password") or ""

        if not login or not password:
            self._send_json(400, {"ok": False, "reason": "missing_credentials"})
            return

        # 完整链路
        try:
            r = unified_login(login, password)
        except RuntimeError as e:
            # 配置错误（缺密钥等），不泄露细节
            self._send_json(500, {"ok": False, "reason": "server_config_error"})
            return
        except Exception:
            self._send_json(500, {"ok": False, "reason": "server_error"})
            return

        # 成功：返回最小必要信息（不含密码、不含完整邮箱）
        if r.ok:
            payload = {
                "ok": True,
                "halo_username": r.halo_username,
                "halo_role": r.halo_role,
                # 实际生效角色（本地可能已有更高角色，登录同步不降权）
                "effective_role": r.effective_role or r.halo_role,
                "display_name": r.forum_display_name or r.forum_username,
                "user_created": r.user_created,
            }
            self._send_json(200, payload)
            return

        # 失败：统一防枚举提示（不区分账号不存在/密码错误）
        self._send_json(401, {
            "ok": False,
            "reason": "invalid_credentials",
            "message": "账号或密码错误",
        })


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), LoginHandler)
    print("统一身份登录 BFF 已启动：http://%s:%d" % (HOST, PORT))
    print("登录端点：POST /api/unified-login")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
