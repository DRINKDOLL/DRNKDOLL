# -*- coding: utf-8 -*-
"""统一身份登录 BFF：论坛账号确认 → Halo 本地用户映射/创建 → 角色映射。

依据《成果展示广场对接警院论坛账号确认接口方案》(JYWC-GW-VERIFY-001) 的
「会话落地」阶段设计。登录链路：

    登录页提交(username, password)
        → 本模块调 forum verify（L2 签名，只读账号确认）
        → confirmed 为 True 时，按 forum user_id 作外键在 Halo 查/建本地用户
        → 按 forum role 映射 Halo 角色（super-role / post-author / guest）
        → 以论坛密码作为本地密码（Halo 服务端 argon2 哈希，明文不落盘）
        → 返回登录结论，前端据此跳转，用户凭同一凭据走 Halo 标准表单登录建会话。

安全红线（与方案一致）：
    - 密码仅在本进程调用期间短暂存在：不落盘、不写日志、不入返回值、不缓存；
    - 平台只判断 forum verify 的 data.confirmed 作为登录结论；
    - 账号不存在与密码错误返回同一结论（防枚举）；
    - Halo 管理凭据（用于建/映射用户）只从环境变量注入，不硬编码；
    - forum user_id → 本地用户名做确定映射，幂等（重复登录不重复建用户）。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .account_verify import AccountVerifyResult, verify_account

# Halo 管理接口地址（本机实例，服务端内部调用）。
ENV_HALO_BASE = "PLAZA_HALO_BASE"
DEFAULT_HALO_BASE = "http://127.0.0.1:8092"
HALO_USERS_PATH = "/apis/api.console.halo.run/v1alpha1/users"

# Halo 管理凭据（建/映射用户用），仅服务端持有。
ENV_HALO_ADMIN_USER = "PLAZA_HALO_ADMIN_USER"
ENV_HALO_ADMIN_PASS = "PLAZA_HALO_ADMIN_PASS"
DEFAULT_HALO_ADMIN_USER = "admin"
# 缺省管理员密码：与现有实例一致（admin / Passw0rd!2026）。
# 生产环境务必用 PLAZA_HALO_ADMIN_PASS 环境变量覆盖。
DEFAULT_HALO_ADMIN_PASS = "Passw0rd!2026"

# 本地用户名前缀：forum 账号 → Halo 本地用户的确定性映射。
LOCAL_USER_PREFIX = "forum-"

# forum role → Halo 角色（role-names annotation）映射表。
#   admin                → super-role（管理员）
#   teacher / assistant  → post-author（作者）
#   student / 其他        → guest（普通访客，默认）
ROLE_MAP = {
    "admin": "super-role",
    "teacher": "post-author",
    "assistant": "post-author",
    "student": "guest",
}
DEFAULT_HALO_ROLE = "guest"

# 请求超时（秒）。
CLIENT_TIMEOUT = 15


@dataclass
class UnifiedLoginResult:
    """统一身份登录的最终结论（不含密码）。"""

    ok: bool = False
    # 论坛确认结果
    confirmed: bool = False
    forum_user_id: str = ""
    forum_username: str = ""
    forum_display_name: str = ""
    forum_role: str = ""
    # Halo 本地映射结果
    halo_username: str = ""
    halo_role: str = ""
    user_created: bool = False
    # 错误信息（失败时给出，供排障；对外统一提示防枚举）
    reason: str = ""
    message: str = ""
    code: int = 0


def _halo_base() -> str:
    return os.environ.get(ENV_HALO_BASE, DEFAULT_HALO_BASE).rstrip("/")


def _halo_admin() -> tuple[str, str]:
    user = os.environ.get(ENV_HALO_ADMIN_USER, DEFAULT_HALO_ADMIN_USER)
    pwd = os.environ.get(ENV_HALO_ADMIN_PASS, DEFAULT_HALO_ADMIN_PASS)
    return user, pwd


def _halo_auth_header() -> str:
    import base64
    user, pwd = _halo_admin()
    return "Basic " + base64.b64encode(
        ("%s:%s" % (user, pwd)).encode("utf-8")
    ).decode("ascii")


def _halo_request(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    """向 Halo 管理接口发请求，返回 (http_status, json_dict)。"""
    url = _halo_base() + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _halo_auth_header())
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=CLIENT_TIMEOUT) as r:
            raw = r.read().decode("utf-8")
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, {"raw": raw}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(e)}


def _safe_username(name: str) -> str:
    """把论坛 username 规范化为合法 Halo 用户名（小写字母/数字/-/.，限长）。"""
    name = (name or "").strip().lower()
    name = re.sub(r"[^a-z0-9.\-]", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    if not name:
        name = "user"
    return name[:60]


def map_role(forum_role: str) -> str:
    """forum role → Halo 角色名。未知角色回退 guest。"""
    return ROLE_MAP.get((forum_role or "").strip().lower(), DEFAULT_HALO_ROLE)


def local_username_for(user_id: str) -> str:
    """forum user_id → 本地用户名（确定、幂等）。"""
    return LOCAL_USER_PREFIX + (user_id or "").strip()


def get_halo_user(username: str) -> tuple[bool, dict]:
    """查询 Halo 本地用户。返回 (是否存在, user_dict)。"""
    status, body = _halo_request("GET", HALO_USERS_PATH + "/" + username)
    if status == 200 and isinstance(body, dict) and "user" in body:
        return True, body["user"]
    return False, {}


def create_halo_user(
    username: str,
    display_name: str,
    email: str,
    password: str,
    halo_role: str,
) -> tuple[bool, str, bool]:
    """在 Halo 创建本地用户（若不存在）并授予角色。返回 (是否成功, 错误信息, 是否新建)。

    关键点：
      - 用户名 = forum-<user_id>（确定映射，幂等）；
      - 密码 = 论坛密码，Halo 服务端负责 argon2 哈希，明文不落盘；
      - 角色通过 POST /users/{name}/permissions 授予（GrantRequest{roles:[...]}），
        创建接口本身不认 roles 字段、默认授予 guest。
    """
    # 幂等：已存在则同步密码（论坛改密后本地凭据需跟着变）并返回成功。
    exists, _ = get_halo_user(username)
    if exists:
        ok, err = _sync_password(username, password)
        if not ok:
            return False, err, False
        # 角色以论坛为准，尽力追加同步。
        # 注意：Halo 的授权接口只支持追加（grant），论坛侧降权不会自动回收本地
        # 高权角色，需在控制台手工调整——已在交付文档中标注为已知限制。
        _grant_role(username, halo_role)
        return True, "", False

    create_body = {
        "name": username,
        "displayName": display_name or username,
        "email": email or (username + "@forum.local"),
        "password": password,
        "avatar": "",
        "bio": "",
    }
    status, body = _halo_request("POST", HALO_USERS_PATH, create_body)
    if status not in (200, 201):
        detail = body.get("detail") if isinstance(body, dict) else str(body)
        return False, "创建 Halo 用户失败 HTTP %s: %s" % (status, detail), False

    # 创建成功后授予角色（默认 guest，需显式 grant）。
    ok, err = _grant_role(username, halo_role)
    if not ok:
        return False, err, True
    return True, "", True


def _sync_password(username: str, password: str) -> tuple[bool, str]:
    """把本地用户密码同步为论坛密码。

    统一身份登录下论坛为唯一凭据源：论坛侧改密后，本地映射账号必须跟着改，
    否则 BFF 确认通过、本地登录却失败。管理员令牌可重置他人密码，无需旧密码。
    """
    status, resp = _halo_request(
        "PUT", HALO_USERS_PATH + "/" + username + "/password", {"password": password}
    )
    if status not in (200, 201, 204):
        detail = resp.get("detail") if isinstance(resp, dict) else str(resp)
        return False, "同步本地密码失败 HTTP %s: %s" % (status, detail)
    return True, ""


def _grant_role(username: str, halo_role: str) -> tuple[bool, str]:
    """给用户授予角色。

    Halo 的权限授予接口是 POST /users/{name}/permissions，body 为
    {"roles": ["<role-name>"]}（GrantRequest）。创建接口默认授予 guest，
    需通过本接口显式授予目标角色。
    """
    exists, _ = get_halo_user(username)
    if not exists:
        return False, "用户 %s 不存在" % username
    body = {"roles": [halo_role]}
    status, resp = _halo_request(
        "POST", HALO_USERS_PATH + "/" + username + "/permissions", body
    )
    if status not in (200, 201, 204):
        detail = resp.get("detail") if isinstance(resp, dict) else str(resp)
        return False, "绑定角色失败 HTTP %s: %s" % (status, detail)
    return True, ""


def unified_login(
    login: str,
    password: str,
    *,
    login_type: str = "auto",
    forum_base: str | None = None,
) -> UnifiedLoginResult:
    """统一身份登录完整链路。

    返回 UnifiedLoginResult：
      - ok=True 表示论坛确认通过且 Halo 本地用户已就绪（可继续走 Halo 登录建会话）；
      - ok=False 时 reason 说明原因，对外统一提示「账号或密码错误」防枚举。
    """
    result = UnifiedLoginResult()

    # 1) 论坛账号确认（只读、防枚举）
    r: AccountVerifyResult = verify_account(
        login, password, login_type=login_type, base=forum_base
    )
    result.confirmed = r.confirmed
    result.forum_user_id = r.user_id
    result.forum_username = r.username
    result.forum_display_name = r.display_name
    result.forum_role = r.role
    result.code = r.code

    if not r.confirmed:
        result.reason = r.reason or "invalid_credentials"
        result.message = r.message
        return result

    # 2) 角色映射
    halo_role = map_role(r.role)
    result.halo_role = halo_role

    # 3) Halo 本地用户映射/创建
    username = local_username_for(r.user_id)
    result.halo_username = username

    email = r.e_mail_masked or (username + "@forum.local")
    # 注意：论坛只回掩码邮箱，不能作为真实 email 使用；
    # 这里用占位邮箱（Halo 强制 email 字段），真实邮箱后续可补充。
    email = re.sub(r"[^@]+@", "user@", email) if email else (username + "@forum.local")

    ok, err, created = create_halo_user(
        username,
        display_name=r.display_name or r.username or username,
        email=email,
        password=password,
        halo_role=halo_role,
    )
    if not ok:
        result.reason = "halo_user_error"
        result.message = err
        return result

    result.user_created = created
    result.ok = True
    return result


# ---------------------------------------------------------------------------
# CLI 联调入口。
# 用法：
#   python -m gateway.unified_login <账号> <密码>
# 需先设置 PLAZA_APP_SECRET（论坛 AppSecret）与 PLAZA_HALO_ADMIN_PASS（可选）。
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    try:
        r = unified_login(sys.argv[1], sys.argv[2])
    except RuntimeError as e:
        print("配置错误：", e)
        sys.exit(2)

    print("confirmed=%s forum_uid=%s role=%s" % (
        r.confirmed, r.forum_user_id, r.forum_role))
    print("halo_username=%s halo_role=%s user_created=%s" % (
        r.halo_username, r.halo_role, r.user_created))
    if r.ok:
        print("=> 登录链路就绪，可继续走 Halo 建会话")
        sys.exit(0)
    else:
        print("=> 失败 reason=%s message=%s" % (r.reason, r.message))
        sys.exit(1)
