#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Halo 站点中文化配置（幂等）。

做的事：
  1) 未安装则调用 /system/setup 完成初始化，语言直接指定 zh-CN
  2) 站点基础配置改为中文：标题、副标题、语言锁 zh-CN
  3) 超级管理员显示名中文化（Administrator -> 管理员）
  4) 示例文章标题中文化（Hello Halo -> 你好，Halo）
重复执行不会产生重复数据，只会把值收敛到目标状态。
"""
import argparse
import base64
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

TITLE_MAP = {
    "Hello Halo": "你好，Halo",
}


def call(base, method, path, body=None, auth=None, timeout=30, raw=False, form=None):
    data = None
    headers = {"Accept": "application/json"}
    if form is not None:
        # /system/setup 的路由按 application/x-www-form-urlencoded 匹配
        data = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if auth:
        token = base64.b64encode(("%s:%s" % auth).encode()).decode()
        headers["Authorization"] = "Basic " + token

    req = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            text = resp.read().decode("utf-8", "replace")
            if raw:
                return resp.status, text
            return resp.status, (json.loads(text) if text.strip() else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        if raw:
            return e.code, text
        try:
            return e.code, json.loads(text)
        except Exception:
            return e.code, text
    except Exception as e:  # 连接未就绪
        return 0, str(e)


def wait_ready(base, seconds=180):
    """服务可访问即返回。注意必须用 Accept: text/html，根路径在 JSON 下会 404。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        req = urllib.request.Request(base + "/", headers={"Accept": "text/html"})
        try:
            with urllib.request.urlopen(req, timeout=5, context=CTX) as resp:
                if resp.status in (200, 302):
                    return True
        except urllib.error.HTTPError as e:
            if e.code in (302, 200):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def ensure_installed(base, username, password, email, title):
    """用 configmaps/system 是否可读来判断是否已完成安装（比 /system/setup 的跳转更可靠）。"""
    auth = (username, password)
    for _ in range(30):
        code, _ = call(base, "GET", "/api/v1alpha1/configmaps/system", auth=auth, timeout=5, raw=True)
        if code == 200:
            print("  实例已安装，跳过初始化")
            return
        break

    payload = {
        "username": username,
        "password": password,
        "email": email,
        "siteTitle": title,
        "language": "zh-CN",
        "externalUrl": base,
    }
    code, body = call(base, "POST", "/system/setup", form=payload, timeout=180, raw=True)
    if code not in (200, 204, 302):
        raise SystemExit("安装失败：%s %s" % (code, body))
    print("  初始化完成（站点标题：%s，语言：zh-CN）" % title)

    # 等待安装结果落库
    for _ in range(30):
        code, _ = call(base, "GET", "/api/v1alpha1/configmaps/system", auth=auth, timeout=5, raw=True)
        if code == 200:
            return
        time.sleep(2)
    raise SystemExit("安装后实例仍不可用")


def unify_basic(base, auth, title, subtitle):
    path = "/apis/console.api.halo.run/v1alpha1/systemconfigs/basic"
    code, cfg = call(base, "GET", path, auth=auth)
    if code != 200 or not isinstance(cfg, dict):
        raise SystemExit("读取基础配置失败：%s %s" % (code, cfg))
    before = dict(cfg)
    cfg["title"] = title
    cfg["subtitle"] = subtitle
    cfg["language"] = "zh-CN"
    cfg["externalUrl"] = base
    if cfg == before:
        print("  站点基础配置已是目标状态，跳过")
        return
    code, body = call(base, "PUT", path, cfg, auth=auth)
    if code not in (200, 204):
        raise SystemExit("写入基础配置失败：%s %s" % (code, body))
    print("  站点标题 → %s" % title)
    print("  站点副标题 → %s" % subtitle)
    print("  站点语言 → zh-CN（浏览器语言不再影响界面语言）")


def unify_admin(base, auth, username, display_name="管理员"):
    path = "/api/v1alpha1/users/%s" % username
    code, user = call(base, "GET", path, auth=auth)
    if code != 200 or not isinstance(user, dict):
        raise SystemExit("读取用户失败：%s" % code)
    spec = user.setdefault("spec", {})
    if spec.get("displayName") == display_name:
        print("  管理员显示名已是「%s」，跳过" % display_name)
        return
    old = spec.get("displayName")
    # 重要：spec.password 是口令哈希，必须原样回传，剔除会导致账号口令被清空
    if not spec.get("password"):
        print("  ! 读取到空口令字段，跳过显示名更新（避免破坏账号）")
        return
    spec["displayName"] = display_name
    code, body = call(base, "PUT", path, user, auth=auth)
    if code not in (200, 204):
        raise SystemExit("更新用户失败：%s %s" % (code, body))

    # 回读确认账号未被破坏
    code, _ = call(base, "GET", path, auth=auth, raw=True)
    if code != 200:
        raise SystemExit("显示名更新后鉴权失效（HTTP %s）" % code)
    print("  管理员显示名 → %s（原：%s）" % (display_name, old))


def unify_posts(base, auth):
    code, page = call(base, "GET", "/apis/content.halo.run/v1alpha1/posts?page=0&size=50", auth=auth)
    if code != 200 or not isinstance(page, dict):
        raise SystemExit("读取文章失败：%s" % code)
    changed = 0
    for item in page.get("items", []):
        spec = item.get("spec", {})
        title = (spec.get("title") or "").strip()
        if title in TITLE_MAP:
            spec["title"] = TITLE_MAP[title]
            code, body = call(base, "PUT", "/apis/content.halo.run/v1alpha1/posts/%s" % item["metadata"]["name"],
                              item, auth=auth)
            if code not in (200, 204):
                print("  ! 文章更新失败：%s %s" % (code, body))
                continue
            print("  示例文章标题 → %s（原：%s）" % (spec["title"], title))
            changed += 1
    if not changed:
        print("  文章标题无需改动")


def unify_post_content(base, auth):
    """正文存放在快照里，需通过控制台接口改写并重新发布。"""
    code, page = call(base, "GET", "/apis/content.halo.run/v1alpha1/posts?page=1&size=50", auth=auth)
    if code != 200 or not isinstance(page, dict):
        raise SystemExit("读取文章失败：%s" % code)
    for item in page.get("items", []):
        name = item["metadata"]["name"]
        code, payload = call(base, "GET",
                             "/apis/api.console.halo.run/v1alpha1/posts/%s/release-content" % name,
                             auth=auth)
        if code != 200 or not isinstance(payload, dict):
            continue
        raw = payload.get("raw") or ""
        rendered = payload.get("content") or ""
        if not any(en in raw or en in rendered for en in TITLE_MAP):
            continue
        body = {k: payload[k] for k in ("raw", "content", "rawType") if k in payload}
        for key in ("raw", "content"):
            for en, zh in TITLE_MAP.items():
                body[key] = body[key].replace(en, zh)
        code, resp = call(base, "PUT",
                          "/apis/api.console.halo.run/v1alpha1/posts/%s/content" % name,
                          body, auth=auth)
        if code not in (200, 204):
            print("  ! 正文更新失败：%s" % code)
            continue
        code, resp = call(base, "PUT",
                          "/apis/api.console.halo.run/v1alpha1/posts/%s/publish" % name,
                          {}, auth=auth)
        if code not in (200, 204):
            print("  ! 重新发布失败：%s" % code)
            continue
        print("  示例文章正文 → 已中文化并重新发布")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--email", default="admin@example.com")
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    args = ap.parse_args()

    if not wait_ready(args.base):
        raise SystemExit("服务未就绪，无法继续")

    auth = (args.username, args.password)
    ensure_installed(args.base, args.username, args.password, args.email, args.title)
    unify_basic(args.base, auth, args.title, args.subtitle)
    unify_admin(args.base, auth, args.username)
    unify_posts(args.base, auth)
    unify_post_content(args.base, auth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
