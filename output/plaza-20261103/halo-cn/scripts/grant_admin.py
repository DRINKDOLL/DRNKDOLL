#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把指定账号设为管理员（授予 super-role），幂等。

为什么需要这个脚本：
    Halo 的账号与其角色绑定保存在运行时数据库（workdir/db/halo-next.mv.db）中，
    数据库属于运行态数据、已被 .gitignore 排除，无法通过 git 复现账号状态。
    因此这里用一段可版本化的脚本把「设为管理员」这一操作固化下来，
    换机器 / 重建实例后执行本脚本即可把账号恢复为管理员。

做的事：
    1) 若账号不存在 → 创建（需要 --password；未给则随机生成并打印一次）
    2) 若账号已存在 → 仅确保具名角色，不重设密码（除非显式 --reset-password）
    3) 授予 super-role（超级管理员，verbs/resources/apiGroups 均为 *）

用法：
    python scripts/grant_admin.py <username> [--password XXX] [--roles super-role]
    python scripts/grant_admin.py fengyukai --password '1qaz0plm'

依赖：仅 Python 标准库。管理凭据优先取环境变量，其次用内置缺省值。
"""
import argparse
import base64
import json
import os
import secrets
import string
import sys
import urllib.error
import urllib.request

HALO_BASE = os.environ.get("HALO_BASE", "http://127.0.0.1:8092")
ADMIN_USER = os.environ.get("PLAZA_HALO_ADMIN_USER", os.environ.get("HALO_ADMIN_USER", "admin"))
ADMIN_PASS = os.environ.get("PLAZA_HALO_ADMIN_PASS", os.environ.get("HALO_ADMIN_PASS", "Passw0rd!2026"))

USERS_PATH = "/apis/api.console.halo.run/v1alpha1/users"


def _auth_header() -> str:
    raw = f"{ADMIN_USER}:{ADMIN_PASS}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _request(method: str, path: str, body=None):
    """返回 (status, text)。HTTP 错误也返回而不抛，便于按状态码分支。"""
    req = urllib.request.Request(HALO_BASE + path, method=method)
    req.add_header("Authorization", _auth_header())
    req.add_header("Content-Type", "application/json")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    try:
        resp = urllib.request.urlopen(req, data=data, timeout=20)
        return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _get_user(username: str):
    status, text = _request("GET", f"{USERS_PATH}/{username}")
    if status == 200:
        payload = json.loads(text)
        # 单用户读取返回 {"user": {...}, "roles": [...]}；列表接口直接返回 User。
        return payload.get("user", payload)
    if status == 404:
        return None
    raise SystemExit(f"查询用户失败：HTTP {status} {text[:300]}")


def _gen_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def ensure_user(username: str, password: str | None, reset_password: bool) -> tuple[bool, str | None]:
    """确保用户存在。返回 (是否新建, 实际使用的密码——仅新建/重设时有值)。"""
    existing = _get_user(username)
    if existing is not None:
        if reset_password:
            if not password:
                password = _gen_password()
            status, text = _request("PUT", f"{USERS_PATH}/{username}/password", {"password": password})
            if status not in (200, 204):
                raise SystemExit(f"重设密码失败：HTTP {status} {text[:300]}")
            print(f"  · 已重设 {username} 的密码")
            return False, password
        print(f"  · 账号 {username} 已存在，保持原密码")
        return False, None

    used = password or _gen_password()
    body = {
        "name": username,
        "displayName": username,
        "email": f"{username}@forum.local",
        "password": used,
        "avatar": "",
        "bio": "",
    }
    status, text = _request("POST", USERS_PATH, body)
    if status not in (200, 201):
        raise SystemExit(f"创建用户失败：HTTP {status} {text[:300]}")
    print(f"  · 已创建账号 {username}")
    return True, used


def grant_roles(username: str, roles: list[str]) -> None:
    """授予角色。Halo 的授权接口为追加语义，重复执行同一角色不会重复生效。"""
    status, text = _request("POST", f"{USERS_PATH}/{username}/permissions", {"roles": roles})
    if status not in (200, 204):
        raise SystemExit(f"授予角色失败：HTTP {status} {text[:300]}")
    print(f"  · 已授予角色：{', '.join(roles)}")


def verify(username: str) -> None:
    user = _get_user(username)
    if user is None:
        raise SystemExit(f"校验失败：账号 {username} 不存在")
    ann = (user.get("metadata") or {}).get("annotations") or {}
    names = ann.get("rbac.authorization.halo.run/role-names", "")
    print(f"  · 当前角色注解：{names}")
    if "super-role" not in names:
        raise SystemExit("校验失败：super-role 未生效")


def main() -> None:
    parser = argparse.ArgumentParser(description="把账号设为管理员（授予 super-role）")
    parser.add_argument("username", help="Halo 用户名")
    parser.add_argument("--password", help="新建账号时的密码；已存在则默认不改")
    parser.add_argument("--roles", default="super-role", help="要授予的角色，逗号分隔（默认 super-role）")
    parser.add_argument("--reset-password", action="store_true", help="对已存在账号也重设密码")
    args = parser.parse_args()

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    print(f"[grant_admin] 目标实例：{HALO_BASE}，账号：{args.username}，角色：{roles}")

    created, used_password = ensure_user(args.username, args.password, args.reset_password)
    grant_roles(args.username, roles)
    verify(args.username)

    print("[grant_admin] 完成")
    if created or args.reset_password:
        # 仅在本次生成了新密码时才提示一次，避免明文长期驻留终端历史。
        print(f"  提示：本次密码为 {used_password}，请妥善保存并及时修改。")


if __name__ == "__main__":
    main()
