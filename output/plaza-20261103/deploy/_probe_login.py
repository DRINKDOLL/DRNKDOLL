# -*- coding: utf-8 -*-
"""线上验证：真实 AppSecret 调论坛账号确认接口，确认是「业务拒绝」而非「签名失败」。"""
import sys
sys.path.insert(0, "/opt/plaza")

from gateway.account_verify import verify_account  # noqa: E402

r = verify_account("probe_not_exist_20261106@example.com", "WrongPass123")
print("confirmed =", r.confirmed)
print("reason    =", r.reason)
print("request_id=", getattr(r, "request_id", ""))
