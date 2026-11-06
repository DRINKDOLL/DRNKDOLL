# -*- coding: utf-8 -*-
"""广场向总平台申请的凭证台账（依据《说明》5.1 / 5.3）。

本文件仅登记「名称与用途」，不存放任何真实密钥。真实 AppSecret 只存
配置中心/密钥管理服务，加密存储、运行时注入环境变量，禁止硬编码。
"""
from __future__ import annotations

import json
import os

# 凭证台账（演示数据，密钥一律用环境变量占位，不写真实值）。
CREDENTIAL_LEDGER = {
    # L1 授权码流程：3 个公共客户端（不含 client_secret，仅 client_id + PKCE）
    "clients": [
        {"client_id": "jy-plaza-miniprogram",
         "type": "公共客户端", "grant": "authorization_code + PKCE",
         "redirect_uri": "https://api.{平台域名}/plaza/callback/miniprogram",
         "secret": None},
        {"client_id": "jy-plaza-h5",
         "type": "公共客户端", "grant": "authorization_code + PKCE",
         "redirect_uri": "https://{平台域名}/plaza/callback/h5",
         "secret": None},
        {"client_id": "jy-plaza-console",
         "type": "公共客户端", "grant": "authorization_code + PKCE",
         "redirect_uri": "https://{平台域名}/plaza/callback/console",
         "secret": None},
    ],
    # L2 平台间互调 AppKey
    "app_keys": [
        {"app_key": "svc-plaza", "role": "广场调用底座/工坊（消费 IF-01~07）",
         "secret_env": "PLAZA_APP_SECRET", "rotation": "90 天轮换，S1 内部核心"},
        {"app_key": "svc-forum", "role": "论坛调用广场 IF-08/09",
         "secret_env": "GW_FORUM_SECRET", "rotation": "季度自查"},
        {"app_key": "svc-study", "role": "自学平台调用广场 IF-08",
         "secret_env": "GW_STUDY_SECRET", "rotation": "季度自查"},
        {"app_key": "svc-lab", "role": "实训工坊调用广场 IF-08 + 预留接口",
         "secret_env": "GW_LAB_SECRET", "rotation": "季度自查"},
    ],
    # 其它凭证
    "internal_sign": {
        "name": "X-Internal-Sign 共享密钥",
        "env": "PLAZA_GW_INTERNAL_SIGN_SECRET",
        "note": "网关与广场业务服务共享，仅服务端持有，不接触令牌明文",
    },
}


def render() -> str:
    return json.dumps(CREDENTIAL_LEDGER, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print(render())
