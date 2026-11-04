"""通过 Halo 控制台接口修正站点外部访问地址，避免直接改库破坏校验注解。"""
import base64
import json
import urllib.request

BASE = "http://127.0.0.1:8092"
USER = "admin"
PWD = "Passw0rd!2026"
NEW_URL = "http://8.138.34.151"

token = base64.b64encode(("%s:%s" % (USER, PWD)).encode()).decode()
HDR = {"Authorization": "Basic " + token, "Content-Type": "application/json"}

url = BASE + "/apis/api.console.halo.run/v1alpha1/configmaps/system"
cm = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=20).read())

data = cm.get("data") or {}
print("配置分组:", list(data.keys()))

basic = json.loads(data["basic"])
print("改前 externalUrl:", basic.get("externalUrl"))
basic["externalUrl"] = NEW_URL
data["basic"] = json.dumps(basic, ensure_ascii=False, separators=(",", ":"))
cm["data"] = data

body = json.dumps(cm, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(url, data=body, headers=HDR, method="PUT")
try:
    resp = urllib.request.urlopen(req, timeout=30)
    print("PUT 状态:", resp.status)
except urllib.error.HTTPError as e:
    print("PUT 失败:", e.code, e.read().decode("utf-8", "replace")[:400])
    raise SystemExit(1)

chk = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=20).read())
print("改后 externalUrl:", json.loads(chk["data"]["basic"]).get("externalUrl"))
