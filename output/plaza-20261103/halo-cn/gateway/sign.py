# -*- coding: utf-8 -*-
"""L2 平台间后台互调签名（HMAC-SHA256）实现。

依据《广场接入说明》4.2 与《鉴权文档》6.3：

  签名要素（请求头）：
    X-App-Key      应用标识，公开
    X-Timestamp    秒级 Unix 时间戳，与服务器偏差 ≤ 300 秒
    X-Nonce        16–32 位随机串，10 分钟内不得重复
    X-Sign-Alg     固定 HMAC-SHA256
    X-Signature    小写十六进制签名值

  规范化签名串（字段以 \\n 分隔，缺失字段以空串占位）：
    appKey \n timestamp \n nonce \n HTTP_METHOD(大写) \n
    path(不含域名与 query) \n canonicalQuery(key 字典序+URL编码) \n sha256Hex(rawBody)

  签名值 = hex(HMAC-SHA256(appSecret, canonicalString))

关键约束（务必遵守）：
  1. 签名基于「原始 body 字节」，序列化完成后再计算签名，签名后不得再改动 JSON
     （含空格、键序）。
  2. GET 的 body 视为空串（bodyHash = sha256("")）。
  3. query 参数需解码后重新编码，避免框架编码差异。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse


# 时间戳允许偏差（秒），与配置 auth.sign.skew 一致，默认 300。
DEFAULT_SKEW = 300
# nonce 去重窗口（秒），与配置 auth.sign.nonce.ttl 一致，默认 600。
DEFAULT_NONCE_TTL = 600
# 固定签名算法标识。
SIGN_ALG = "HMAC-SHA256"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_query(query_string: str) -> str:
    """把 query string 规范化为「key 字典序 + URL 编码」的字符串。

    规则：先按 key 升序排序；key 与 value 都做 RFC3986 百分比编码（用 quote 的
    安全字符集，空格编码为 %20 而非 +）；多值 key 按出现顺序保留；最终形如
    "k1=v1&k2=v2"（不含前导 ?）。

    实现说明：urllib.parse.parse_qsl 默认已解码一次（把 %XX 还原为原始字节），
    再对 key/value 重新 quote，即可消除不同框架「编码 or 不编码」的差异。
    """
    pairs = urllib.parse.parse_qsl(query_string, keep_blank_values=True)
    # 排序：仅按 key 升序，value 相同时保持原相对顺序（稳定排序）。
    pairs.sort(key=lambda kv: kv[0])
    parts = []
    for k, v in pairs:
        parts.append(
            "%s=%s" % (urllib.parse.quote(k, safe=""), urllib.parse.quote(v, safe=""))
        )
    return "&".join(parts)


def build_canonical(app_key: str, timestamp: str, nonce: str,
                    method: str, path: str, query: str, body: bytes) -> str:
    """拼接规范化签名串。

    body 传原始字节；GET/无 body 时传 b""。
    """
    q = canonical_query(query) if query else ""
    body_hash = _sha256_hex(body or b"")
    return "\n".join([
        app_key,
        timestamp,
        nonce,
        method.upper(),
        path,
        q,
        body_hash,
    ])


def sign(app_secret: str, canonical: str) -> str:
    """计算 HMAC-SHA256 签名，返回小写十六进制。"""
    return hmac.new(app_secret.encode("utf-8"), canonical.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def build_signature(app_key: str, app_secret: str, method: str, path: str,
                    query: str, body: bytes, timestamp: int | None = None,
                    nonce: str | None = None) -> dict:
    """调用方：生成一套完整的 L2 签名请求头。

    返回 dict，包含 X-App-Key / X-Timestamp / X-Nonce / X-Sign-Alg / X-Signature。
    timestamp 不传则取当前 Unix 秒；nonce 不传则生成 32 位随机十六进制串。
    """
    ts = str(timestamp if timestamp is not None else int(time.time()))
    if nonce is None:
        nonce = base64.b64encode(_sha256_hex(str(time.time_ns()).encode()).encode()).decode()[:32]
    canonical = build_canonical(app_key, ts, nonce, method, path, query, body)
    return {
        "X-App-Key": app_key,
        "X-Timestamp": ts,
        "X-Nonce": nonce,
        "X-Sign-Alg": SIGN_ALG,
        "X-Signature": sign(app_secret, canonical),
    }


class SignatureError(Exception):
    """签名校验失败，携带网关错误码（40105/40106/40107/40108）。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class NonceStore:
    """nonce 去重存储的抽象接口。

    生产环境用 Redis（SETNX，key=nonce，TTL=nonce.ttl）；本地演示用内存 dict。
    实现要点：nonce 必须先于签名校验写入（SETNX），防止攻击者用错误签名反复
    试探而不消耗 nonce（《说明》9.2）。
    """

    def consume(self, nonce: str, ttl: int) -> bool:
        """尝试占用一个 nonce。返回 True 表示首次使用（占用成功），False 表示重复。"""
        raise NotImplementedError


class MemoryNonceStore(NonceStore):
    """内存 nonce 去重（仅演示/单机，不跨进程）。"""

    def __init__(self):
        self._seen: dict[str, float] = {}

    def consume(self, nonce: str, ttl: int) -> bool:
        now = time.time()
        # 顺带清理过期的 nonce，避免内存无限增长。
        self._seen = {k: v for k, v in self._seen.items() if now - v < ttl}
        if nonce in self._seen:
            return False
        self._seen[nonce] = now
        return True


class AppKeyStore:
    """AppKey -> AppSecret 的映射接口。

    生产环境从配置中心/密钥管理服务读取，密钥加密存储、运行时注入；
    本地演示从环境变量/配置文件读取。
    """

    def secret_of(self, app_key: str) -> str | None:
        raise NotImplementedError


class DictAppKeyStore(AppKeyStore):
    def __init__(self, mapping: dict[str, str]):
        self._mapping = mapping

    def secret_of(self, app_key: str) -> str | None:
        return self._mapping.get(app_key)


class SignatureVerifier:
    """服务方：校验 L2 签名。

    校验顺序（与《说明》4.2 一致）：
      1. 解析并校验 5 个头齐全；
      2. 校验 X-Sign-Alg 为 HMAC-SHA256；
      3. 校验 X-Timestamp 在 [now-skew, now+skew] 窗口内（否则 40106）；
      4. 校验 X-Nonce 去重（重复则 40107）；
      5. 用 appKey 对应 appSecret 重算签名，比对（不一致 40105）；
      6. appKey 未知/停用则 40108。
    """

    def __init__(self, app_keys: AppKeyStore, nonce_store: NonceStore | None = None,
                 skew: int = DEFAULT_SKEW, nonce_ttl: int = DEFAULT_NONCE_TTL):
        self._app_keys = app_keys
        self._nonce = nonce_store or MemoryNonceStore()
        self._skew = skew
        self._nonce_ttl = nonce_ttl

    def verify(self, headers: dict, method: str, path: str, query: str,
               body: bytes) -> str:
        """校验签名，返回 app_key（校验通过）或抛出 SignatureError。"""
        app_key = (headers.get("X-App-Key") or "").strip()
        timestamp = (headers.get("X-Timestamp") or "").strip()
        nonce = (headers.get("X-Nonce") or "").strip()
        alg = (headers.get("X-Sign-Alg") or "").strip()
        signature = (headers.get("X-Signature") or "").strip()

        if not all([app_key, timestamp, nonce, alg, signature]):
            raise SignatureError("40105", "签名头缺失")

        if alg.upper() != SIGN_ALG:
            raise SignatureError("40105", "不支持的签名算法")

        # 时间戳窗口校验
        try:
            ts = int(timestamp)
        except ValueError:
            raise SignatureError("40106", "时间戳非整数")
        if abs(time.time() - ts) > self._skew:
            raise SignatureError("40106", "时间戳超出窗口")

        # nonce 去重（先于签名校验占用）
        if not self._nonce.consume(nonce, self._nonce_ttl):
            raise SignatureError("40107", "nonce 重复")

        # appKey 校验
        secret = self._app_keys.secret_of(app_key)
        if secret is None:
            raise SignatureError("40108", "AppKey 不存在或停用")

        # 重算签名并比对
        canonical = build_canonical(app_key, timestamp, nonce, method, path, query, body)
        expected = sign(secret, canonical)
        if not hmac.compare_digest(expected, signature):
            raise SignatureError("40105", "签名不匹配")

        return app_key
