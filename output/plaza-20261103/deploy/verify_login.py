"""端到端校验：登录后台 -> 访问受保护接口 -> 读站点设置。
凭据写在文件内、不走命令行参数，避免出现在 ps / 审计日志里。
"""
import http.cookiejar
import os
import re
import urllib.parse
import urllib.request

BASE = os.environ.get("HALO_BASE", "http://127.0.0.1")
USER = os.environ.get("HALO_USER", "admin")
PWD = os.environ.get("HALO_PWD", "Passw0rd!2026")

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

html = op.open(BASE + "/login?authentication_required", timeout=15).read().decode("utf-8", "replace")
m = re.search(r'name="_csrf"\s+value="([^"]+)"', html)
if not m:
    raise SystemExit("未取到 CSRF token")
csrf = m.group(1)

body = urllib.parse.urlencode({
    "_csrf": csrf,
    "username": USER,
    "password": PWD,
}).encode()
req = urllib.request.Request(BASE + "/login", data=body,
                             headers={"Content-Type": "application/x-www-form-urlencoded"})
try:
    resp = op.open(req, timeout=15)
    print("登录请求 HTTP", resp.status, "->", resp.geturl())
except urllib.error.HTTPError as e:
    print("登录失败 HTTP", e.code)
    raise SystemExit(1)

names = [c.name for c in cj]
print("会话 Cookie:", ", ".join(names) if names else "(无)")

# 受保护接口：需要登录态
api = BASE + "/apis/api.console.halo.run/v1alpha1/users/-"
try:
    me = op.open(api, timeout=15)
    import json
    d = json.load(me)
    meta = d.get("metadata", {})
    print("当前登录用户:", meta.get("name"), "| 显示名:", (d.get("spec") or {}).get("displayName"))
    print("角色:", [r for r in (d.get("spec") or {}).get("roles", [])])
except urllib.error.HTTPError as e:
    print("受保护接口返回", e.code, "（未取得登录态）")
    raise SystemExit(1)
