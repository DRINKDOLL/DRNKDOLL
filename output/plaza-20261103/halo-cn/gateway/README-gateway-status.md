# 成果展示广场 · 网关接入状态说明（三大要素闭环）

> 对齐口径：与同架构平台（考试平台）的网关接入结论一致——**入站 / 出站 / 上游切换
> 三大要素全部完成并实测**，并补充可交叉确认的验收断言。
> 最后核验：2026-11-06（功能联动闭环 + 真实内部签名密钥接入）。

## 一、结论对照

| 要素 | 结论口径 | 广场侧落地 | 状态 |
| --- | --- | --- | --- |
| ① 入站 | 网关 → 平台：严格验签，伪造请求 403 | 服务态 L2 签名 + **用户态 X-Internal-Sign 校验** | ✅ 完成并实测 |
| ② 出站 | 平台 → 网关：L2 签名，账号确认 confirmed | `account_verify.verify_account`（真实外网链路） | ✅ 完成并实测 |
| ③ 上游切换 | 桩 → 真实 BFF（管理员已完成） | 统一身份登录 BFF 8095（真实论坛账号 → 本地会话） | ✅ 完成并实测 |
| ④ 功能联动 | 网关注入身份 → 广场校验 → 业务执行 | `identity_injector`（注入方）+ `identity.parse_identity`（校验方）+ 真实密钥 | ✅ 本轮接线并实测 |

**剩余建议（非阻塞）**：以 `scripts/verify_gateway.py` 的 **35 条**运行结果交叉确认；
**90 天内做首次密钥轮换**（`svc-plaza` / `svc-forum` / `svc-study` / `svc-lab` /
内部签名密钥）。

## 二、要素 1 · 入站（严格验签，伪造请求 403）

广场侧入站分两种鉴权模型，都在 `gateway/server.py`（端口 8094）实现：

### （1）服务态（`/api/v1/internal/**`）
消费方（论坛 / 自学 / 工坊）用 AppKey + L2 HMAC-SHA256 签名调用，只读。
校验顺序：五头齐全 → 算法 → 时间戳窗口 300s → nonce 去重 → AppKey 台账 → 签名比对；
随后路由白名单（默认拒绝）→ 限流。

### （2）用户态（`/api/v1/user/**`）
经网关转发的浏览器/终端请求，由**网关注入**可信身份头
（`X-User-Id` / `X-User-Role` / `X-Client-Id` / `X-Token-Exp` / `X-Request-Id` /
`X-Auth-Mode` / `X-Internal-Sign`）。广场业务服务：

1. 校验 `X-Internal-Sign`（HMAC-SHA256，字段固定顺序）——缺失或错误一律
   **403 / 40303**（视为绕过网关直连）；
2. 校验 `X-Token-Exp` 过期 —— **401 / 40103**；
3. 水平越权校验（`enforce_owner`，不得仅凭 `X-User-Id` 放行）——非作者且非管理员
   **403 / 70002**，管理员豁免。

> 本轮修复：此前 `identity.py`（身份解析 + 内部签名校验 + 越权拦截）**没有任何调用点**，
> 用户态入站实际不可验证。现已在 `server.py` 接线，图片要素 1「伪造请求 403」可被实测断言。

## 三、要素 2 · 出站（L2 签名，账号确认 confirmed）

`gateway/account_verify.py::verify_account()`：以 `jy-plaza-svc` 身份，用 L2 五头签名调用
`POST http://8.138.246.181/answer/api/v1/account/verify`，只读判断 `data.confirmed`。

- 正向：`admin / Admin@12345` → `HTTP 200`、`confirmed=True`、`uid=1`、`role=admin`。
- 反向：密码错误 / 账号不存在（合规格式）→ 均 `401 / 40104`（**防枚举**，同包络同提示）。
- AppSecret 经环境变量 `PLAZA_APP_SECRET` 注入，兜底读 `gateway/configs/secrets.json`
  （已入 `.gitignore`），不硬编码。

## 四、要素 3 · 上游切换（桩 → 真实 BFF）

统一身份登录链路（`gateway/unified_login.py` + `gateway/login_server.py`，端口 8095）
已由**桩切到真实 BFF**：登录页提交论坛账号密码 → BFF 走真实论坛 `verify` 确认 →
按 `forum-<user_id>` 映射/创建 Halo 本地用户 → 按论坛角色映射（admin→super-role，
teacher/assistant→post-author，其他→guest）→ 前端换用户名后走 Spring Security 标准登录建会话。
详见 `gateway/README-unified-login.md`。

## 五、功能联动（网关注入 → 广场校验 → 业务执行）

「功能联动」指用户态链路的完整闭环：**网关侧把 L1 用户身份注入请求头 → 广场业务
服务校验内部签名与越权 → 执行业务并返回**。它由两个角色构成：

| 角色 | 模块 | 职责 |
| --- | --- | --- |
| 注入方（网关） | `gateway/identity_injector.py` | 按固定字段顺序生成 `X-User-Id`/`X-User-Role`/`X-Token-Exp`/…/`X-Internal-Sign` |
| 校验方（广场） | `gateway/identity.py` + `server.py` 的 `/api/v1/user/**` | 校验内部签名 → 令牌时效 → 水平越权 → 业务返回 |

**密钥接入**：本轮把真实内部签名共享密钥写入 `gateway/configs/secrets.json` 的
`internal_sign.secret`（已入 `.gitignore`）。解析优先级统一为
**环境变量 `PLAZA_GW_INTERNAL_SIGN_SECRET` > 密钥文件 > 演示兜底**，
由 `config.resolve_internal_sign_secret()` 单点提供，`server.py`（校验方）与
`identity_injector.py`（注入方）、`scripts/verify_gateway.py`（验收）三处共用同一解析，
**杜绝两侧密钥不一致导致联动整体 403**。

> 本轮修复：此前只有校验方、没有注入方，且服务端密钥是模块级演示值
> `internal-sign-demo`，与 `config.py` 的生产口径（仅读环境变量）不一致，真实密钥
> 无处落。现补齐注入器并统一密钥解析；用旧演示密钥签名已被拒绝（403/40303），
> 证明已切换到真实密钥。

联动验证方式（任选其一）：

```bash
# 1) CLI 主动触发一次联动（默认作者本人场景）
python -m gateway.identity_injector --user-id 10231 --role student
#    越权场景（应 403/70002）
python -m gateway.identity_injector --user-id 88888 --role student --path /api/v1/user/works/work-1001

# 2) 验收脚本内含 4 条联动断言（作者 200 / 越权 403-70002 / 未签名 403-40303 / 两侧签名串一致）
python scripts/verify_gateway.py
```

## 六、交叉验收（35 条，对照结论口径）

```
cd halo-cn
python scripts/verify_gateway.py          # 服务态 + 用户态 + 工具 + IF-07 + 出站桩，31 条
node scripts/verify_unified_login.js      # 统一身份登录端到端，10 条
```

`verify_gateway.py` 覆盖：

- **服务态 L2**（17 条）：缺头 / 错密钥 / 未知 AppKey / 算法非法 / 时间戳过旧 / 超前 /
  nonce 重放 / 越权路由 403-70007 / 授权放行 / 列表 / 详情 / 不存在 404-70005 /
  分页 page=0 / size=101 上限 / 按项目 / 按团队 / 团队归属。
- **用户态入站**（7 条）：缺 `X-Internal-Sign` 403-40303 / 伪造签名 403-40303 /
  本人 200 / 水平越权 403-70002 / 管理员豁免 200 / 令牌过期 401-40103 / 作品不存在 404-70005。
- **功能联动闭环**（4 条）：注入方触发链路作者 200 / 越权 403-70002 / 未注入签名 403-40303 /
  注入器与校验方签名串一致。
- **签名工具**（2 条）：`canonical_query` 排序稳定 / GET 空 body 规范化串。
- **IF-07 降级**（1 条）：正常认证 / 不可用沿用待核验 / 无历史不认证 三分支。
- **出站账号确认**（2 条，本地桩）：签名串正确 + 正向 `confirmed=True` / 反向 `confirmed=False`。

## 七、密钥轮换（90 天）

| AppKey | 用途 | 密钥环境变量 | 轮换 |
| --- | --- | --- | --- |
| `svc-plaza` | 广场调用底座/工坊（消费 IF-01~07） | `PLAZA_APP_SECRET` | **90 天（S1 核心）** |
| `svc-forum` | 论坛调用广场 IF-08/09 | `GW_FORUM_SECRET` | 季度自查 |
| `svc-study` | 自学平台调用广场 IF-08 | `GW_STUDY_SECRET` | 季度自查 |
| `svc-lab` | 工坊调用广场 IF-08 + 预留接口 | `GW_LAB_SECRET` | 季度自查 |
| 内部签名 | 网关注入身份头校验 | `PLAZA_GW_INTERNAL_SIGN_SECRET` | 与网关约定同步轮换 |

轮换要点：新密钥先「双活」（新旧并存一段重叠期）→ 切换消费方 → 下线旧密钥；
**历史密钥曾通过截图分发，务必在首次轮换时一并作废**。

## 八、已知限制（非阻塞）

- 服务态数据源当前为内存样例（`DataProvider`），生产需替换为 Halo 内容接口。
- nonce 去重 / 限流为内存单进程实现，生产需 Redis；`gateway_config.yaml` 未接入运行时装载。
- `events.py` 事件回调链路待对接方就绪（`identity.py` 用户态入站与联动注入已接线）。
- Halo 授权接口是**替换**语义（非追加），登录同步已按「不降权」策略实现
  （`unified_login.sync_role`，目标角色等级低于本地现有角色时跳过）。
  **论坛侧降权不自动回收本地高权角色**，需控制台手工处理。
- 该策略的副作用：本地手工授予的高权角色会持续保留，不会因论坛侧降权而失效；
  回收权限必须在 `/console` 手工改角色。这是「宁可保留也不误降管理员」的刻意取舍。
