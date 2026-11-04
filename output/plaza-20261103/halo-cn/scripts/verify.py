#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""中文化验收：接口断言 + 页面可见文本英文残留扫描。

输出 run/verify.json，供验证报告页读取。
"""
import argparse
import base64
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

# 允许保留的英文：品牌名、技术专名、URL 片段
WHITELIST = {
    "halo", "halo.run", "github", "rss", "api", "url", "uri", "markdown", "html",
    "css", "js", "json", "http", "https", "www", "com", "cn", "org", "run",
    "qq", "wechat", "email", "id", "ai", "demo", "seo", "sso", "cdn", "sdk",
    "microsoft", "windows", "chrome", "edge", "safari", "firefox", "linux", "macos",
}

results = []


def record(name, ok, detail):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print("  %s %s：%s" % ("✔" if ok else "✘", name, detail))


def call(base, path, auth=None, timeout=20):
    req = urllib.request.Request(base + path, headers={"Accept": "application/json"})
    if auth:
        token = base64.b64encode(("%s:%s" % auth).encode()).decode()
        req.add_header("Authorization", "Basic " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def visible_text(markup):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", markup)
    text = re.sub(r"(?s)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def english_tokens(text):
    tokens = re.findall(r"[A-Za-z][A-Za-z'’.\-]{2,}", text)
    leaked = []
    for t in tokens:
        if t.lower().strip(".-") in WHITELIST:
            continue
        if t not in leaked:
            leaked.append(t)
    return leaked


def read_basic(base, auth):
    """读取站点基础配置。兼容两种返回：settings/system 聚合体，或 configmap 的 data.basic 字符串。"""
    for path, use_auth in (("/api/v1alpha1/settings/system", None),
                           ("/api/v1alpha1/configmaps/system", auth)):
        code, body = call(base, path, auth=use_auth)
        if code != 200 or not (body or "").strip():
            continue
        try:
            obj = json.loads(body)
        except Exception:
            continue
        if isinstance(obj.get("basic"), dict):
            return obj["basic"]
        data = obj.get("data") or {}
        if isinstance(data.get("basic"), str):
            try:
                return json.loads(data["basic"])
            except Exception:
                continue
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--out", default="run/verify.json")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    auth = (args.username, args.password)

    # 1) 站点基础配置
    cfg = read_basic(base, auth)
    record("站点语言锁定", cfg.get("language") == "zh-CN", "language=%s" % cfg.get("language"))
    record("站点标题为中文字段", any("\u4e00" <= ch <= "\u9fff" for ch in (cfg.get("title") or "")),
           "title=%s" % cfg.get("title"))

    # 2) 页面 <html lang>
    code, page = call(base, "/", timeout=30)
    lang = re.search(r'<html[^>]*\slang="([^"]+)"', page or "")
    record("首页 html lang", bool(lang) and lang.group(1).lower().startswith("zh"),
           "lang=%s" % (lang.group(1) if lang else "未声明"))

    # 3) 首页可见文本英文扫描
    text = visible_text(page or "")
    leaked = english_tokens(text)
    record("首页无英文残留", not leaked, "残留：%s" % (", ".join(leaked[:8]) if leaked else "无"))
    record("首页含中文字符", bool(re.search(r"[\u4e00-\u9fff]", text)), "中文字符数=%d" % len(re.findall(r"[\u4e00-\u9fff]", text)))

    # 4) 页脚校对
    record("页脚已中文化", "版权所有" in text and "All Rights Reserved" not in text,
           "页脚片段：%s" % (text[-80:] if text else ""))

    # 5) 控制台 HTML lang
    code, console = call(base, "/console", timeout=30)
    clang = re.search(r'<html[^>]*\slang="([^"]+)"', console or "")
    record("控制台 html lang", bool(clang) and clang.group(1).lower().startswith("zh"),
           "lang=%s" % (clang.group(1) if clang else "未声明"))

    # 6) 管理员显示名
    code, u = call(base, "/api/v1alpha1/users/%s" % args.username, auth=auth)
    disp = ""
    if code == 200:
        try:
            disp = json.loads(u).get("spec", {}).get("displayName", "")
        except Exception:
            pass
    record("管理员显示名中文化", any("\u4e00" <= ch <= "\u9fff" for ch in disp), "displayName=%s" % disp)

    ok = all(r["ok"] for r in results)
    payload = {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base": base,
               "passed": sum(1 for r in results if r["ok"]), "total": len(results),
               "ok": ok, "results": results, "page_text_sample": text[:300]}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n  验收结果：%d/%d 通过%s" % (payload["passed"], payload["total"], "" if ok else "（存在未通过项）"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
