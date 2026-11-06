# -*- coding: utf-8 -*-
"""配置装载：auth.* 与 plaza.* 配置项。

依据《广场接入说明》5.2 配置项清单。auth.* 由网关/总平台统一下发，广场侧
只需确认 plaza.* 与 IF-08 限流、路由白名单等本平台配置。

优先级：环境变量 > gateway_config.yaml（若存在）> 内置默认值。
"""
from __future__ import annotations

import json
import os


# 默认值（与《说明》5.2 建议值对齐）。
DEFAULTS = {
    # auth.*（网关/总平台下发）
    "auth.token.ttl": 7200,          # access_token 有效期（秒）
    "auth.code.ttl": 300,            # 授权码有效期（秒）
    "auth.state.ttl": 600,           # state 有效期（秒）
    "auth.introspect.timeout": 800,  # 自省超时（毫秒），广场服务不直连，仅网关
    "auth.sign.skew": 300,           # L2 时间窗（秒）
    "auth.sign.nonce.ttl": 600,      # nonce 去重窗口（秒）
    "auth.rate.user.qps": 20,        # 单令牌限流
    "auth.rate.app.qps": 200,        # 单 AppKey 限流
    # plaza.*（广场侧确认）
    "plaza.if08.rate": 100,          # IF-08 接口限流（QPS）
    "plaza.media.sign.ttl": 1800,    # 媒体签名 URL 有效期（秒，30 分钟）
}

# 网关内部签名密钥环境变量名（仅服务端持有，不落代码/前端/镜像明文）。
ENV_INTERNAL_SIGN_SECRET = "PLAZA_GW_INTERNAL_SIGN_SECRET"

# 本地密钥文件（与 account_verify 共用同一份 configs/secrets.json，已入 .gitignore）。
# 结构：{"app_keys": {...}, "internal_sign": {"secret": "..."}}
SECRETS_PATH = os.path.join(os.path.dirname(__file__), "configs", "secrets.json")

# 显式演示兜底值：仅当既无环境变量、又无密钥文件时启用（离线验收）。
# 生产必须经环境变量或 600 权限密钥文件注入，不得落到此分支。
DEMO_INTERNAL_SIGN_SECRET = "internal-sign-demo"


def _read_internal_sign_from_file() -> str:
    """从本地密钥文件读取内部签名密钥（无文件/字段则返回空串）。"""
    if not os.path.exists(SECRETS_PATH):
        return ""
    try:
        with open(SECRETS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (data.get("internal_sign") or {}).get("secret", "") or ""
    except (OSError, ValueError):
        return ""


def resolve_internal_sign_secret(allow_demo: bool = True) -> str:
    """解析内部签名密钥。优先级：环境变量 > 密钥文件 > 演示兜底。

    - allow_demo=True  时三级兜底，保证离线联调/验收可跑（默认）。
    - allow_demo=False 时不使用演示值；仍无配置则抛 RuntimeError（生产调用口径）。

    网关（注入方）与广场业务服务（校验方）必须解析出**同一个值**，
    否则用户态联动会因 X-Internal-Sign 校验失败而整体 403。
    """
    secret = os.environ.get(ENV_INTERNAL_SIGN_SECRET, "")
    if secret:
        return secret
    secret = _read_internal_sign_from_file()
    if secret:
        return secret
    if allow_demo:
        return DEMO_INTERNAL_SIGN_SECRET
    raise RuntimeError(
        "未配置内部签名密钥：请设置环境变量 %s 或在 %s 写入 internal_sign.secret"
        % (ENV_INTERNAL_SIGN_SECRET, SECRETS_PATH)
    )


def internal_sign_secret_source() -> str:
    """返回当前内部签名密钥的来源（env / file / demo），便于启动自检与排障。"""
    if os.environ.get(ENV_INTERNAL_SIGN_SECRET, ""):
        return "env"
    if _read_internal_sign_from_file():
        return "file"
    return "demo"

# 广场自身 AppKey/AppSecret 环境变量（调用底座/工坊时使用）。
ENV_PLAZA_APP_KEY = "PLAZA_APP_KEY"
ENV_PLAZA_APP_SECRET = "PLAZA_APP_SECRET"


def _load_yaml(path: str) -> dict:
    """极简 YAML 读取：仅支持 `key: value` 与 `key: "value"` 的扁平结构，
    足够覆盖本模块的扁平配置项，避免引入 PyYAML 依赖。"""
    out: dict[str, object] = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            out[k] = v
    return out


class Config:
    def __init__(self, yaml_path: str | None = None):
        self._data = dict(DEFAULTS)
        # 1) YAML 覆盖
        if yaml_path:
            for k, v in _load_yaml(yaml_path).items():
                self._data[k] = v
        # 2) 环境变量覆盖（PLAZA_CFG_<key>，点号 -> 下划线）
        for k in list(self._data.keys()):
            env_key = "PLAZA_CFG_" + k.replace(".", "_").upper()
            if env_key in os.environ:
                self._data[k] = os.environ[env_key]
        # 归一化数值型
        for k in self._data:
            if isinstance(DEFAULTS.get(k), int):
                try:
                    self._data[k] = int(self._data[k])
                except (ValueError, TypeError):
                    pass

    def get(self, key: str):
        return self._data.get(key, DEFAULTS.get(key))

    def get_int(self, key: str) -> int:
        v = self.get(key)
        try:
            return int(v)
        except (ValueError, TypeError):
            return int(DEFAULTS.get(key, 0))

    def internal_sign_secret(self) -> str:
        """内部签名密钥（生产口径：不使用演示兜底）。未配置则抛错。"""
        return resolve_internal_sign_secret(allow_demo=False)


# 全局单例（默认不读文件，仅默认值 + 环境变量）。
config = Config()
