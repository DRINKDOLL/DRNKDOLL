# -*- coding: utf-8 -*-
"""广场对接警院论坛「账号确认接口」的调用封装（接口层）。

依据《成果展示广场对接警院论坛账号确认接口方案》(JYWC-GW-VERIFY-001)：

    接口：POST http://8.138.246.181/answer/api/v1/account/verify
    用途：用户用警院论坛账号登录广场时，经统一网关做「只读账号确认」，
          返回「账号密码是否正确、是谁」的最小身份信息；广场据此建立
          本平台自己的会话。

职责边界（本模块只做接口层）：
    - 复用 gateway/sign.py 的 L2 签名（规范化串与论坛侧 account_verify_client.py 一致）；
    - 组装请求体、调用接口、解析响应；
    - 把「是否确认 + 最小身份」映射为结构化的 AccountVerifyResult；
    - 会话建立（create_platform_session）仅留接口占位，由后续接入 Halo 登录时填充。

安全红线：
    - AppSecret 只从环境变量注入，不硬编码、不写日志；
    - 密码仅在本进程调用期间短暂存在，不落盘、不写日志、不入会话、不缓存；
    - 只判断 data.confirmed 作为登录结论，不依赖 data.reason 做业务分流；
    - 账号不存在与密码错误返回同一结论（防枚举），广场侧统一提示。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import ENV_PLAZA_APP_KEY, ENV_PLAZA_APP_SECRET
from .sign import build_signature

# 本地密钥文件（可选兜底）。结构同论坛侧 configs/secrets.json：
#   {"app_keys": {"jy-plaza-svc": {"secret": "..."}}}
# 优先级：环境变量 PLAZA_APP_SECRET > 本文件。生产建议只用环境变量。
SECRETS_PATH = os.path.join(os.path.dirname(__file__), "configs", "secrets.json")

# 接口地址（可被环境变量覆盖，便于联调切换桩/真实环境）。
ENV_GATEWAY_BASE = "JY_GATEWAY_BASE"
DEFAULT_GATEWAY_BASE = "http://8.138.246.181"
VERIFY_PATH = "/answer/api/v1/account/verify"

# 默认 AppKey（广场服务身份）。可被环境变量 PLAZA_APP_KEY 覆盖。
DEFAULT_APP_KEY = "jy-plaza-svc"

# 客户端超时（秒）。网关 S 级 3 s，客户端给足余量。
CLIENT_TIMEOUT = 15


@dataclass
class AccountVerifyResult:
    """账号确认接口的解析结果（结构化）。

    平台侧只以 `confirmed` 作为登录判定依据，其余字段仅在有值时填充。
    """
    confirmed: bool = False
    user_id: str = ""
    username: str = ""
    display_name: str = ""
    role: str = ""
    e_mail_masked: str = ""
    account_source: str = ""
    status: str = ""
    request_id: str = ""

    # 原始信息（用于排障，不含密码）。
    http_status: int = 0
    code: int = 0
    message: str = ""
    reason: str = ""
    raw: dict = field(default_factory=dict)


def _secret(app_key: str) -> str:
    """读取 AppSecret。优先级：环境变量 > 本地 configs/secrets.json。未配置即抛错。"""
    secret = os.environ.get(ENV_PLAZA_APP_SECRET, "")
    if secret:
        return secret
    if os.path.exists(SECRETS_PATH):
        try:
            with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            secret = data.get("app_keys", {}).get(app_key, {}).get("secret", "")
            if secret:
                return secret
        except (OSError, ValueError):
            pass
    raise RuntimeError(
        "未配置广场 AppSecret（环境变量 %s 或 %s）" % (ENV_PLAZA_APP_SECRET, SECRETS_PATH)
    )


def _app_key(app_key: str | None) -> str:
    key = app_key or os.environ.get(ENV_PLAZA_APP_KEY, "") or DEFAULT_APP_KEY
    return key


def _gateway_base(base: str | None) -> str:
    return base or os.environ.get(ENV_GATEWAY_BASE, DEFAULT_GATEWAY_BASE)


def _build_headers(app_key: str, app_secret: str, body: str) -> dict:
    """用 L2 五头签名，并附加 Content-Type。"""
    headers = build_signature(
        app_key, app_secret, "POST", VERIFY_PATH, "", body.encode("utf-8")
    )
    headers["Content-Type"] = "application/json"
    return headers


def verify_account(
    login: str,
    password: str,
    app_key: str | None = None,
    app_secret: str | None = None,
    login_type: str = "auto",
    client_id: str = "",
    base: str | None = None,
    timeout: int = CLIENT_TIMEOUT,
) -> AccountVerifyResult:
    """调用账号确认接口，返回结构化结果。

    参数：
        login        论坛用户名或邮箱（1~100 字符，首尾去空格）
        password     明文密码（8~32 字符），仅论坛进程内 bcrypt 比对
        app_key      平台 AppKey，默认 jy-plaza-svc（或环境变量 PLAZA_APP_KEY）
        app_secret   平台 AppSecret，默认从环境变量 PLAZA_APP_SECRET 读取
        login_type   auto / username / email，默认 auto
        client_id    调用方业务标识（审计用），默认取 app_key
        base         网关地址，默认 http://8.138.246.181（或环境变量 JY_GATEWAY_BASE）

    返回：
        AccountVerifyResult；调用异常（网络/超时）时返回 confirmed=False、
        code=0、reason 说明原因，不会抛出 HTTP 异常。
    """
    key = _app_key(app_key)
    secret = app_secret or _secret(key)
    cid = client_id or key
    login = (login or "").strip()
    body = json.dumps(
        {
            "login": login,
            "pass": password,
            "login_type": login_type,
            "client_id": cid,
        },
        separators=(",", ":"),
    )
    headers = _build_headers(key, secret, body)
    url = _gateway_base(base).rstrip("/") + VERIFY_PATH

    result = AccountVerifyResult(request_id="")

    try:
        req = urllib.request.Request(url, data=body.encode("utf-8"),
                                     method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result.http_status = r.status
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        result.http_status = e.code
        raw = e.read().decode("utf-8", "ignore")
        try:
            resp = json.loads(raw)
        except Exception:
            result.reason = "gateway_unparseable"
            result.raw = {"raw": raw[:200]}
            return result
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        result.http_status = 0
        result.reason = "network_error"
        result.message = str(e)
        return result

    return _parse(result, resp)


def _parse(result: AccountVerifyResult, resp: dict) -> AccountVerifyResult:
    """解析响应为结构化结果。失败包络与成功包络都按统一结构解析。"""
    result.raw = resp
    result.code = resp.get("code", 0)
    result.message = resp.get("message", "")

    data = resp.get("data") or {}
    result.confirmed = data.get("confirmed") is True
    result.reason = data.get("reason", "")

    # 仅当 confirmed 时才填充身份字段（失败时论坛只回 confirmed=false + reason）。
    if result.confirmed:
        result.user_id = str(data.get("user_id", ""))
        result.username = data.get("username", "")
        result.display_name = data.get("display_name", "")
        result.role = data.get("role", "")
        result.e_mail_masked = data.get("e_mail_masked", "")
        result.account_source = data.get("account_source", "")
        result.status = data.get("status", "")
    result.request_id = data.get("request_id", "")

    return result


# ---------------------------------------------------------------------------
# 会话建立：接口占位（后续接入 Halo 登录流程时填充）。
# 职责：据 AccountVerifyResult 建立广场自己的会话，绝不保存密码、
#       不缓存接口返回的敏感字段。
# ---------------------------------------------------------------------------
def create_platform_session(result: AccountVerifyResult):
    """占位：建立广场侧会话。

    对接 Halo 登录时在此实现，例如：
        create_platform_session(user_id=result.user_id,
                                username=result.username,
                                role=result.role)
    当前仅作接口契约占位，不落任何实现。
    """
    raise NotImplementedError(
        "会话建立待接入 Halo 登录流程时实现（本模块只封装接口层）"
    )


# ---------------------------------------------------------------------------
# CLI 联调入口（仿论坛侧 account_verify_client.py）。
# 用法：
#   python -m gateway.account_verify <账号> <密码> [AppKey]
# 需先设置环境变量 PLAZA_APP_SECRET（与 JY_GATEWAY_BASE 可选）。
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    key = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        r = verify_account(sys.argv[1], sys.argv[2], app_key=key)
    except RuntimeError as e:
        print("配置错误：", e)
        sys.exit(2)

    print("HTTP", r.http_status)
    print("code=%s message=%s" % (r.code, r.message))
    if r.confirmed:
        print("confirmed=True  uid=%s username=%s role=%s source=%s" % (
            r.user_id, r.username, r.role, r.account_source))
    else:
        print("confirmed=False  reason=%s" % (r.reason or "(无)"))

    print("\n=> 可以建立本平台会话" if r.confirmed else "\n=> 拒绝登录")
    sys.exit(0 if r.confirmed else 1)
