# -*- coding: utf-8 -*-
"""线上冒烟：account_verify 模块可用性 + 缺密钥拦截 + gateway 配置读取。"""
import os
import sys

sys.path.insert(0, "/opt/plaza")

from gateway.account_verify import verify_account, AccountVerifyResult  # noqa: E402

print("[1] import ok:", verify_account.__name__, "/", AccountVerifyResult.__name__)

os.environ.pop("PLAZA_APP_SECRET", None)
try:
    verify_account("probe", "probe")
    print("[2] UNEXPECTED 未拦截")
except RuntimeError as exc:
    print("[2] 缺密钥已拒绝:", str(exc)[:70])

from gateway.config import (  # noqa: E402
    ENV_PLAZA_APP_KEY, ENV_PLAZA_APP_SECRET,
)
print("[3] 环境变量常量:", ENV_PLAZA_APP_KEY, "/", ENV_PLAZA_APP_SECRET)

try:
    from gateway.config import Settings  # noqa: E402
    s = Settings.from_env() if hasattr(Settings, "from_env") else Settings()
    keys = sorted(k for k in dir(s) if not k.startswith("_"))
    print("[4] 配置对象键:", ",".join(keys[:10]))
except Exception as exc:  # noqa: BLE001
    print("[4] 配置读取告警:", repr(exc)[:80])

# 网关服务是否在监听
import socket  # noqa: E402
s = socket.socket()
s.settimeout(3)
print("[5] 8094 可连接:", s.connect_ex(("127.0.0.1", 8094)) == 0)
s.close()
