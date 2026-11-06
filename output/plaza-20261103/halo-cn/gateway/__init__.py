# -*- coding: utf-8 -*-
"""警院WeChat 网关接入模块（成果展示广场侧）。

本包实现《成果展示广场统一身份与网关接入说明文档》(JYWC-GW-INTEGRATION-001 V1.1)
所推荐的网关接入方案，纯 Python 标准库实现，无第三方依赖。

模块组成：
  - sign.py      L2 平台间互调签名（HMAC-SHA256）与校验
  - identity.py  网关注入身份头解析与 X-Internal-Sign 校验
  - errors.py    网关层错误码透传 + 广场业务层错误码（70000 段）
  - config.py    配置项装载（auth.* / plaza.*）
"""
