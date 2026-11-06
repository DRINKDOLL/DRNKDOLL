# 统一身份登录（论坛账号 → 广场会话）· 实施说明

模块：`gateway/unified_login.py`（链路编排）、`gateway/login_server.py`（登录页调用的 HTTP BFF）、
登录页前端（`workdir/templates/gateway_fragments/{login.html, common.html}`）。

## 一、链路总览

```
登录页 (8092 /login)
  │  ① 提交(username, password)，前端先拦一次
  ▼
BFF POST /api/unified-login (8095)
  │  ② forum verify（L2 签名、只读确认、防枚举）
  │  ③ forum user_id → 本地用户名 forum-<user_id>（确定映射、幂等）
  │  ④ 不存在则创建 Halo 本地用户；已存在则同步密码/角色
  │  ⑤ 返回 {ok, halo_username, halo_role, display_name}
  ▼
登录页
  │  ⑥ 把表单 username 换成 forum-<user_id>，密码不变（RSA 加密）
  │  ⑦ 原生提交 POST /login（Spring Security 建会话）
  ▼
Halo 会话（/uc 个人中心；admin 角色可进 /console）
```

设计与《成果展示广场对接警院论坛账号确认接口方案》一致：**BFF 不代建会话**，只做
「确认 + 映射 + 建本地用户」前半段，会话仍由 Spring Security 走标准登录建立，
不绕过 CSRF 与安全上下文。

## 二、角色映射

| 论坛 role | Halo 角色 | 说明 |
| --- | --- | --- |
| `admin` | `super-role` | 管理员，可进 `/console` |
| `teacher` / `assistant` | `post-author` | 作者，可发文章 |
| `student` / 其他 | `guest` | 普通访客 |

授予方式：`POST /apis/api.console.halo.run/v1alpha1/users/{name}/permissions`，
body `{"roles":["<role>"]}`。创建接口本身不认 `roles` 字段（默认 `guest`），必须单独授予。

### 授权语义：替换，不是追加（重要）

该接口是**替换**语义——服务端把用户的全部角色整体换成请求里的集合，并非追加。
（`UserServiceImpl` 日志：`Updated roles for user: existingRoles=[A], roles=[B]`，
旧的 RoleBinding 会被 GC 删除；请求集合里带上已有角色名会返回 400「名称重复」。）

因此每次统一登录都无条件同步论坛角色，会造成**降权**：论坛侧为 `student`（映射 `guest`）
的账号，其本地手工授予的 `super-role` / `post-author` 会被登录冲掉，
表现为「设为管理员后一登录又变回访客」。

**修复（`sync_role` 不降权同步）**：登录同步时比较目标角色与本地现有角色的权限等级
（`ROLE_RANK`：super-role 100 > post-author 50 > guest 10）：

- 目标等级 **≥** 现有最高等级 → 执行同步（正常升权、横向切换）；
- 目标等级 **<** 现有最高等级 → **跳过**，保护既有更高权限不被登录覆盖。

由此形成两条明确边界：

- **自动升级**：论坛升权（student → teacher）在下次登录自动生效；
- **手工回收**：论坛降权**不会**自动回收本地高权角色，需在控制台手工调整
  （这是刻意的取舍——宁可保留权限也不误降管理员）。

BFF 响应与 CLI 输出附带 `effective_role`（登录后**实际生效**角色），
与 `halo_role`（论坛角色映射值）可能不同，排障时以 `effective_role` 为准。

## 三、账号与凭据

- 本地用户名：`forum-<user_id>`，与论坛 `user_id` 一一对应，重复登录不重复建号。
- 本地密码：**等于论坛密码**。已存在用户每次登录都会调用
  `PUT /apis/api.console.halo.run/v1alpha1/users/{name}/password` 同步密码，
  因此论坛改密后广场侧无需人工干预。
- 邮箱：论坛只回掩码邮箱（`a***@jspi.edu.cn`），不能作为真实邮箱使用，
  本地统一落占位邮箱 `user@<域名>`；真实邮箱待论坛侧放开字段后补充。

## 四、登录页交互

- 默认「统一身份登录」：提示使用警院论坛（WeChat 五平台）账号，首次登录自动开通本站账号。
- 兜底「使用本地账号登录」：一键切回原生账号密码登录，用于
  `admin` / `student` 等本地演示账号，以及 BFF 未启动时的降级场景。
- 失败提示统一为「账号或密码错误」（不区分账号不存在/密码错误，防枚举）；
  BFF 不可达时提示「统一身份服务暂不可用」，并引导改用本地账号登录。
- 前端实现要点：表单提交**先 preventDefault**，BFF 返回后再调用 `form.submit()`。
  ⚠️ 不能在 submit 事件处理中调用 `form.requestSubmit()`——浏览器会视为重复提交而静默忽略，
  表现为「点了登录没反应、也不报错」。此坑已踩过并修复。

## 五、部署与启动

- BFF：`python -m gateway.login_server`，监听 `0.0.0.0:8095`，纯标准库，无第三方依赖。
  - 环境变量：`PLAZA_LOGIN_PORT`（默认 8095）、`PLAZA_LOGIN_HOST`（默认 0.0.0.0）、
    `PLAZA_LOGIN_ORIGINS`（可选，默认放行 `127.0.0.1/localhost:8092`）。
  - Origin 校验策略：白名单命中，或与请求 `Host` **同主机不同端口**（支持局域网 IP 访问）。
- 已并入开机自启：`halo-cn/autostart_task.bat`（GBK + CRLF）同时拉起 Halo(8092) 与 BFF(8095)，
  已注册计划任务「警院成果广场自启动」；启动项 `启动警院成果广场.bat` 内容同步。
- 登录页前端通过 `location.hostname:8095` 拼 BFF 地址，因此 127.0.0.1 与局域网 IP 访问都可用。

## 六、验证结果（2026-11-06）

验收脚本：`scripts/verify_unified_login.js`（Playwright，10 项断言全部通过）

| 用例 | 结论 |
| --- | --- |
| 登录页展示统一身份提示、存在本地账号兜底入口 | 通过 |
| 论坛管理员账号登录 → 会话身份 `forum-1` | 通过 |
| 登录后可进入 `/console/dashboard` | 通过 |
| 控制台无 JS 报错 | 通过 |
| 错误密码 → 统一提示「账号或密码错误」且不跳转 | 通过 |
| 切换本地模式 → `admin / Passw0rd!2026` 正常登录 | 通过 |
| BFF 直连：正向 200、密码错 401、账号不存在 401（同包络） | 通过 |
| 用户清理：仅剩 `admin`、`student`、`forum-1` 与系统账号 | 通过 |

复跑：`cd halo-cn && node scripts/verify_unified_login.js`

## 七、安全红线

- 密码只在 BFF 进程内短暂存在：不落盘、不写日志、不入返回值、不缓存。
- BFF 只信 `verify` 的 `data.confirmed` 作为登录结论，不按论坛错误明细做业务分流。
- 账号不存在与密码错误返回同一 HTTP 状态与同一提示。
- Halo 管理凭据（建号/改密用）仅服务端持有，默认取环境变量
  `PLAZA_HALO_ADMIN_USER` / `PLAZA_HALO_ADMIN_PASS`，生产环境必须覆盖默认值。
