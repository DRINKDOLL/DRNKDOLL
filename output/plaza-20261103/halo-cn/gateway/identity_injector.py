# -*- coding: utf-8 -*-
"""网关侧身份头注入器（用户态功能联动的「触发方」）。

分工：
  - 网关（注入方，本模块）：把校验通过的 L1 用户身份，按固定字段顺序计算
    X-Internal-Sign，随请求头注入广场业务服务。
  - 广场（校验方，`identity.parse_identity`）：校验 X-Internal-Sign、令牌时效、
    水平越权，再执行业务。

两侧必须解析到**同一个**内部签名密钥（`PLAZA_GW_INTERNAL_SIGN_SECRET`，或
`configs/secrets.json` 的 `internal_sign.secret`），否则联动整体 403（40303）。

本模块既是可复用的注入实现，也提供 CLI，便于联调时主动触发一次完整联动：

    python -m gateway.identity_injector --user-id 10231 --role student \
        --path /api/v1/user/works/work-1001
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request

from .config import internal_sign_secret_source, resolve_internal_sign_secret
from .identity import INTERNAL_SIGN_FIELDS, _internal_sign_value

# 广场业务服务默认地址（用户态联动入口）。
DEFAULT_PLAZA_BASE = "http://127.0.0.1:8094"


def build_identity_headers(
    user_id: str,
    role: str = "student",
    *,
    client_id: str = "jy-plaza-miniprogram",
    token_exp: int | None = None,
    request_id: str = "",
    auth_mode: str = "user",
    secret: str | None = None,
) -> dict[str, str]:
    """构造网关注入广场服务的可信身份头（含 X-Internal-Sign）。

    字段顺序严格遵循 `identity.INTERNAL_SIGN_FIELDS`，与校验方保持一致。
    """
    secret = secret or resolve_internal_sign_secret(allow_demo=True)
    headers = {
        "X-User-Id": str(user_id),
        "X-User-Role": role,
        "X-Client-Id": client_id,
        "X-Token-Exp": str(token_exp if token_exp is not None else int(time.time()) + 7200),
        "X-Request-Id": request_id or ("gw-%d" % time.time_ns()),
        "X-Auth-Mode": auth_mode,
    }
    # 必填字段必须齐全，否则签名与校验两侧的规范化串会不一致。
    assert set(INTERNAL_SIGN_FIELDS).issubset(headers.keys())
    headers["X-Internal-Sign"] = _internal_sign_value(headers, secret)
    return headers


def call_user_api(
    path: str,
    *,
    user_id: str,
    role: str = "student",
    base: str = DEFAULT_PLAZA_BASE,
    method: str = "GET",
    secret: str | None = None,
    timeout: int = 8,
    **kw,
) -> tuple[int, dict]:
    """以网关注入的身份头调用广场用户态接口，返回 (HTTP 状态, 响应体)。

    这是「功能联动」的完整触发路径：
        注入身份头 → 广场校验内部签名 → 令牌时效 → 水平越权 → 业务返回。
    """
    headers = build_identity_headers(user_id, role, secret=secret, **kw)
    req = urllib.request.Request(base.rstrip("/") + path, method=method)
    for k, v in headers.items():
        req.add_header(k, v)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def _normalize_path(path: str) -> str:
    """修正 shell 环境对以 `/` 开头参数的路径改写（如 Git Bash / MSYS）。

    例：`/api/v1/user/works/work-1001` 可能被改写成
    `C:/Program Files/Git/api/v1/user/works/work-1001`；此处还原为 `/api/...`。
    """
    if path.startswith("/"):
        return path
    idx = path.find("/api/")
    if idx >= 0:
        return path[idx:]
    return "/" + path.lstrip("/")


def main() -> int:
    ap = argparse.ArgumentParser(description="网关身份头注入 / 用户态联动触发")
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--role", default="student")
    ap.add_argument("--path", default="/api/v1/user/works/work-1001")
    ap.add_argument("--base", default=DEFAULT_PLAZA_BASE)
    ap.add_argument("--client-id", default="jy-plaza-miniprogram")
    ap.add_argument("--token-exp", type=int, default=None)
    ap.add_argument("--auth-mode", default="user")
    args = ap.parse_args()

    path = _normalize_path(args.path)

    print("密钥来源：%s" % internal_sign_secret_source())
    headers = build_identity_headers(
        args.user_id, args.role, client_id=args.client_id,
        token_exp=args.token_exp, auth_mode=args.auth_mode)
    print("注入身份头：")
    for k in list(INTERNAL_SIGN_FIELDS) + ["X-Internal-Sign"]:
        v = headers.get(k, "")
        print("  %-16s %s" % (k + ":", v[:24] + ("…" if len(v) > 24 else "")))

    status, body = call_user_api(
        path, user_id=args.user_id, role=args.role, base=args.base,
        client_id=args.client_id, token_exp=args.token_exp, auth_mode=args.auth_mode)
    print("\nHTTP %s" % status)
    print(json.dumps(body, ensure_ascii=False, indent=2)[:600])
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
