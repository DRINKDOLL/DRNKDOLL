#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""成果展示广场「成果管理」后端代理服务。

只依赖 Python 标准库（http.server + urllib），不引入任何第三方依赖。

职责：把前台「编辑 / 删除」按钮的操作转发给 Halo 控制台接口，管理员的
Basic 凭据只保存在本进程（服务端），不会下发到浏览器，避免把密码暴露在前端。

对外暴露的最小 JSON 接口（供 theme-earth 模板里的 Alpine 组件调用）：
    GET  /api/manage/achievements                列出全部成果（含可编辑字段）
    PUT  /api/manage/achievements/{name}         更新成果（标题 / 简介 / 封面）
    PUT  /api/manage/achievements/{name}/recycle 把成果移入回收站（软删除）

说明：
  - 更新走 Halo 控制台接口 PUT /apis/api.console.halo.run/v1alpha1/posts/{name}，
    需要携带文章当前的 metadata.version 做乐观锁，否则会报 DuplicateKeyException。
    这里会先 GET 一次文章拿最新 spec + metadata，再合并要改的字段回写。
  - 删除用「回收站」（PUT .../recycle），不物理删除，符合「删除前确认 + 可恢复」。
  - 正文（content）不做改动，仅更新标题 / 简介 / 封面这三项展示字段。

启动：
    python scripts/manage_server.py                 # 监听 127.0.0.1:8093
    HALO_MANAGE_PORT=8093 HALO_BASE=http://127.0.0.1:8092 \
        HALO_USER=admin HALO_PASS=Passw0rd!2026 python scripts/manage_server.py
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HALO_BASE = os.environ.get("HALO_BASE", "http://127.0.0.1:8092")
HALO_USER = os.environ.get("HALO_USER", "admin")
HALO_PASS = os.environ.get("HALO_PASS", "Passw0rd!2026")
PORT = int(os.environ.get("HALO_MANAGE_PORT", "8093"))
HOST = os.environ.get("HALO_MANAGE_HOST", "0.0.0.0")

# 允许跨域的前台来源（本机演示只放行 Halo 自身与局域网地址）
ALLOWED_ORIGINS = {
    "http://127.0.0.1:8092",
    "http://localhost:8092",
    "http://10.1.1.239:8092",
}

AUTH = "Basic " + base64.b64encode(("%s:%s" % (HALO_USER, HALO_PASS)).encode()).decode()

CONSOLE = "/apis/api.console.halo.run/v1alpha1/posts"
CONTENT = "/apis/api.content.halo.run/v1alpha1/posts"


def halo(method, path, body=None):
    """调用 Halo 接口，返回 (status, 解析后的 JSON 或原始字符串)。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HALO_BASE + path, data=data, method=method)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:1000]


def clean_metadata(md):
    """去掉服务端管理的字段，保留 name / version / labels / annotations 等。"""
    out = dict(md)
    for key in (
        "creationTimestamp", "deletionTimestamp", "generation",
        "managedFields", "lastModifyTime", "observedVersion",
    ):
        out.pop(key, None)
    return out


def list_achievements():
    status, data = halo("GET", CONTENT + "?page=1&size=100&sort=spec.publishTime,desc")
    if status != 200:
        return status, data
    items = []
    for p in data.get("items", []):
        spec = p.get("spec", {})
        excerpt = spec.get("excerpt", {}) or {}
        items.append({
            "name": p.get("metadata", {}).get("name"),
            "slug": spec.get("slug"),
            "title": spec.get("title"),
            "cover": spec.get("cover") or "",
            "excerpt": excerpt.get("raw") or (p.get("status", {}).get("excerpt") or ""),
            "pinned": bool(spec.get("pinned")),
            "publish": bool(spec.get("publish")),
        })
    return 200, {"items": items}


def update_achievement(name, payload):
    """更新标题 / 简介 / 封面，保留正文、分类、标签不变，更新后重新发布。

    Halo 的 updatePost 会先把文章置回草稿（phase=DRAFT），所以这里在
    更新成功后必须再调用一次 publish，否则详情页会看不到改动。
    """
    status, post = halo("GET", CONTENT + "/" + name)
    if status != 200:
        return status, post
    spec = dict(post.get("spec", {}))
    metadata = clean_metadata(post.get("metadata", {}))

    # 只更新三个展示字段，其余保持原样
    if "title" in payload:
        spec["title"] = payload["title"]
    if "excerpt" in payload:
        spec["excerpt"] = {"autoGenerate": False, "raw": payload["excerpt"]}
    if "cover" in payload:
        spec["cover"] = payload["cover"] or ""

    # 带上当前正文一起提交（PostRequest 要求 content 非空）
    status, head = halo("GET", CONSOLE + "/" + name + "/head-content")
    if status != 200:
        return status, head
    body = {
        "post": {"spec": spec, "metadata": metadata},
        "content": {
            "raw": head.get("raw") or "",
            "content": head.get("content") or "",
            "rawType": head.get("rawType") or "markdown",
        },
    }
    status, res = halo("PUT", CONSOLE + "/" + name, body)
    if status != 200:
        return status, res

    # 更新成功后重新发布，让改动对前台可见
    pub_status, pub_res = halo("PUT", CONSOLE + "/" + name + "/publish", {})
    if pub_status != 200:
        return pub_status, {"error": "update ok but publish failed", "detail": pub_res}
    return status, res


def recycle_achievement(name):
    return halo("PUT", CONSOLE + "/" + name + "/recycle", {})


class Handler(BaseHTTPRequestHandler):
    server_version = "ManageServer/1.0"

    def _cors(self):
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")

    def _send_json(self, status, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._cors()
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", "ignore")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/manage/achievements":
            status, data = list_achievements()
            self._send_json(status, data)
            return
        self._send_json(404, {"error": "not found"})

    def do_PUT(self):
        m = re.fullmatch(r"/api/manage/achievements/([^/]+)/recycle", self.path)
        if m:
            status, data = recycle_achievement(m.group(1))
            self._send_json(status, data)
            return
        m = re.fullmatch(r"/api/manage/achievements/([^/]+)", self.path)
        if m:
            payload = self._read_body()
            status, data = update_achievement(m.group(1), payload)
            self._send_json(status, data)
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, fmt, *args):  # 精简日志
        sys.stderr.write("[manage] %s %s\n" % (self.command, self.path))


def main():
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print("成果管理代理已启动：http://%s:%d" % (HOST, PORT))
    print("Halo 后端：%s（用户 %s）" % (HALO_BASE, HALO_USER))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
