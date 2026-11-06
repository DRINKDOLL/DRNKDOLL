# -*- coding: utf-8 -*-
"""网关注入身份头解析与 X-Internal-Sign 校验。

依据《广场接入说明》4.1 与《鉴权文档》6.2.3、D5：

网关注入广场服务的可信身份头：
    X-User-Id      论坛用户主键
    X-User-Role    角色列表（逗号分隔）
    X-Client-Id    客户端标识
    X-Token-Exp    令牌过期时间戳
    X-Request-Id   全链路追踪 ID
    X-Auth-Mode    鉴权模式：user / service / user+service
    X-Internal-Sign 对上述字段按固定顺序计算的内部签名

关键边界（务必遵守）：
  1. 广场业务服务不得接触令牌明文，只信任网关注入的身份头。
  2. 必须校验 X-Internal-Sign，未校验或校验失败一律 403（40303），视为绕过网关直连。
  3. 同时做水平越权校验（比对资源 owner，不得仅凭 X-User-Id 放行）。
  4. L1（用户）与 L2（服务）凭证禁止混用。
"""
from __future__ import annotations

import hmac
import hashlib
import time

from . import sign as _sign
from .errors import biz


# 参与内部签名的字段顺序（固定，与网关约定一致，见《说明》4.1）。
INTERNAL_SIGN_FIELDS = (
    "X-User-Id",
    "X-User-Role",
    "X-Client-Id",
    "X-Token-Exp",
    "X-Request-Id",
    "X-Auth-Mode",
)


class Identity:
    """解析后的网关注入身份。"""

    def __init__(self, user_id: str, roles: list[str], client_id: str,
                 token_exp: int | None, request_id: str, auth_mode: str):
        self.user_id = user_id
        self.roles = roles
        self.client_id = client_id
        self.token_exp = token_exp
        self.request_id = request_id
        self.auth_mode = auth_mode

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_any_role(self, roles: tuple[str, ...]) -> bool:
        return any(r in self.roles for r in roles)


def _internal_sign_value(headers: dict, secret: str) -> str:
    """按固定字段顺序计算 X-Internal-Sign。"""
    parts = [headers.get(f, "") for f in INTERNAL_SIGN_FIELDS]
    canonical = "\n".join(parts)
    return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def parse_identity(headers: dict, internal_sign_secret: str,
                   require_internal_sign: bool = True) -> Identity:
    """解析网关注入的身份头并校验内部签名。

    调用方应捕获 InternalSignError（或其 code）并返回 403/40303。

    参数：
      headers                 请求头 dict（key 需与网关注入的原始大小写一致，或先归一化）
      internal_sign_secret    网关与广场共享的内部签名密钥（仅服务端持有）
      require_internal_sign   为 False 时跳过校验（仅本地联调），生产必须 True

    异常：
      InternalSignError  校验失败（对应 40303）
    """
    provided = headers.get("X-Internal-Sign", "").strip()
    if require_internal_sign:
        if not provided:
            raise InternalSignError("缺少 X-Internal-Sign，疑似绕过网关直连")
        expected = _internal_sign_value(headers, internal_sign_secret)
        if not hmac.compare_digest(expected, provided):
            raise InternalSignError("X-Internal-Sign 校验失败")

    user_id = headers.get("X-User-Id", "")
    roles = [r for r in (headers.get("X-User-Role", "") or "").split(",") if r]
    client_id = headers.get("X-Client-Id", "")
    token_exp_raw = headers.get("X-Token-Exp", "")
    try:
        token_exp = int(token_exp_raw) if token_exp_raw else None
    except ValueError:
        token_exp = None
    request_id = headers.get("X-Request-Id", "")
    auth_mode = headers.get("X-Auth-Mode", "user")

    return Identity(user_id, roles, client_id, token_exp, request_id, auth_mode)


class InternalSignError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


# 角色定义（总纲 GR-01 四级角色 + 访客态），供水平越权/角色校验使用。
ROLE_STUDENT = "student"
ROLE_ASSISTANT = "assistant"      # 助教
ROLE_TEACHER = "teacher"
ROLE_ADMIN = "admin"

# 两级审核角色约束（GF-03）：助教仅初审，老师/管理员终审。
REVIEW_INITIAL = (ROLE_ASSISTANT, ROLE_TEACHER, ROLE_ADMIN)   # 初审资格
REVIEW_FINAL = (ROLE_TEACHER, ROLE_ADMIN)                      # 终审资格


def enforce_owner(identity: Identity, resource_owner_uid: str) -> None:
    """水平越权校验：资源 owner 必须与 X-User-Id 一致，否则 403（70002）。

    管理员可豁免（但需二次留痕），其余角色强制比对。
    """
    if identity.has_role(ROLE_ADMIN):
        return
    if identity.user_id != resource_owner_uid:
        raise biz_error("70002")


def biz_error(code: str, request_id: str = "") -> Exception:
    """构造广场业务错误异常。为与 errors.py 解耦，这里返回一个带 code 的异常。"""
    from .errors import BizError, biz_http
    return BizError(code, biz_http(code), biz(code, request_id).get("message", ""))
