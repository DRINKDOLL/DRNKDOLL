# 警院成果展示广场 —— 服务器部署说明

**访问地址**：http://8.138.34.151/
**管理后台**：http://8.138.34.151/console

## 一、架构

```
公网 :80  ──►  Nginx ──┬─ /            ──►  Halo 2.27.2  127.0.0.1:8092
                       │                      └── H2 数据库 + workdir
                       └─ /api/manage/ ──►  成果管理代理  127.0.0.1:8093
                            （需登录 Halo 后台才放行）
```

- Nginx 监听 80（同时是默认虚拟主机，覆盖系统欢迎页）
- Halo 只绑定回环地址 `127.0.0.1:8092`，不直接对外暴露
- 成果管理代理只绑定 `127.0.0.1:8093`，公网无法直连，只能经 `/api/manage/` 且必须带有效登录会话
- 运行环境：Alibaba Cloud Linux 3 / x86_64 / 2C1.8G，JDK 21.0.13（Temurin），Python 3.11（代理）

## 二、目录与文件

| 路径 | 说明 |
|---|---|
| `/opt/jdk21/` | JDK 21 运行时（独立安装，不污染系统包） |
| `/opt/plaza/halo.jar` | Halo 2.27.2 主程序 |
| `/opt/plaza/config/application.yaml` | 站点配置（端口、工作目录、模板路径、日志） |
| `/opt/plaza/workdir/` | 数据目录：`db/` 数据库、`static/` 站内图片、`themes/` 主题、`templates/` 定制模板、`plugins/` 插件 |
| `/opt/plaza/logs/halo.log` | 应用日志（滚动） |
| `/opt/plaza/backup/` | 数据库与主题备份 |
| `/opt/plaza/manage/manage_server.py` | 成果管理代理（编辑 / 删除转发到 Halo 控制台接口） |
| `/opt/plaza/config/manage.env` | 代理的运行参数与管理员凭据（权限 600，仅 root 可读） |
| `/etc/systemd/system/plaza.service` | Halo 服务单元（开机自启、异常自动重启） |
| `/etc/systemd/system/manage.service` | 管理代理服务单元（同上） |
| `/etc/nginx/conf.d/plaza.conf` | 反向代理配置（含 `/api/manage/` 登录门禁） |
| `/var/log/nginx/plaza.access.log` | 访问日志 |

## 三、常用运维命令

```bash
systemctl status plaza          # 查看应用状态
systemctl restart plaza         # 重启应用（改配置后必须重启）
systemctl restart manage        # 重启成果管理代理（改 manage.env 后）
journalctl -u plaza -n 100      # 若标准输出异常，看这里
journalctl -u manage -n 50      # 代理日志（记录每次 GET/PUT）
tail -f /opt/plaza/logs/halo.log  # 实时看应用日志

systemctl reload nginx          # 改 Nginx 配置后热加载
nginx -t                        # 改配置后先校验语法
```

## 四、备份与恢复数据库

应用使用 H2 单文件数据库，**复制前必须先停服务**，否则可能拷到损坏副本。

```bash
# 备份
systemctl stop plaza
cp -a /opt/plaza/workdir/db/halo-next.mv.db /opt/plaza/backup/halo-next.mv.db.$(date +%Y%m%d%H%M%S)
systemctl start plaza

# 恢复
systemctl stop plaza
cp -a /opt/plaza/backup/<备份文件> /opt/plaza/workdir/db/halo-next.mv.db
systemctl start plaza
```

H2 控制台（排查数据问题时用，需先停服务）：

```bash
/opt/jdk21/bin/java -Dloader.main=org.h2.tools.Shell -cp /opt/plaza/halo.jar \
  org.springframework.boot.loader.launch.PropertiesLauncher \
  -url "jdbc:h2:/opt/plaza/workdir/db/halo-next;MODE=MySQL" \
  -user admin -password 123456 \
  -sql "SELECT name FROM extensions LIMIT 5"
```

## 五、本次迁移做过的适配（重要）

从 Windows 本机迁移到 Linux，有三处必须处理，否则会出现隐性故障：

1. **插件路径失效**
   数据库里插件的 `pluginUri` 原本是 `file:///C:/Users/.../plugins/xxx.jar`，Linux 上无法解析，导致 10 个插件全部加载失败并持续刷 ERROR。
   已批量改写为 `file:///opt/plaza/workdir/plugins/xxx.jar`，现全部 `STARTED`。

2. **站点外部访问地址**
   Halo 优先使用数据库里的「外部访问地址」设置（`configmaps/system` 的 `basic.externalUrl`），**YAML 里的 `halo.external-url` 会被它覆盖**。
   已改为 `http://8.138.34.151`，RSS、Sitemap 里的绝对链接因此正确。

3. **HTTP Basic 认证（本轮已调整，与「成果管理」有关，务必看懂）**
   Halo 内部开启了 Basic（`basic-auth.disabled: false`），因为管理代理要用它在回环内调控制台接口。
   为防止公网拿账号密码直接调管理接口，Nginx 在边缘把外部请求的 `Authorization: Basic ...` **整段剥掉**
   （`map $http_authorization $plaza_auth`），只放行 Bearer 等其它方案。实测：公网带 Basic 访问控制台接口返回 302，
   回环直连带 Basic 返回 200——这正是预期。
   **不要为了"方便"把 Nginx 里那段 `map`/`proxy_set_header Authorization` 删掉**，否则等于把管理员账号密码暴露成 HTTP Basic 入口。

## 六、成果管理（前台编辑 / 删除）

前台卡片和详情页上的「编辑 / 删除」按钮是本期新增功能，链路如下：

```
浏览器（已登录 Halo 后台）→ /api/manage/achievements
      → Nginx auth_request 校验会话（未登录直接 401）
      → 管理代理 127.0.0.1:8093（用 manage.env 里的凭据调 Halo 控制台接口）
      → Halo：PUT /posts/{name} 更新标题/简介/封面，再 PUT /posts/{name}/publish 重新发布
      → 删除走 /posts/{name}/recycle（进回收站，可恢复，不物理删除）
```

要点：

- 按钮只对**已登录且具备 `system:posts:manage` 权限**的用户显示（页面里 `.is-manager` 控制），匿名访问看不到。
- 代理只改标题、简介、封面三个展示字段，不动正文、分类、标签。
- 更新后必须重新 `publish`，否则 Halo 会把文章置为草稿、前台看不到改动——代理里已处理。
- 代理的凭据在 `/opt/plaza/config/manage.env`（600）。改管理员密码后**必须同步改这里**并 `systemctl restart manage`。
- 单独重启代理：`systemctl restart manage`；看日志：`journalctl -u manage -n 50`。

## 七、安全建议

- **立即修改管理员密码**：当前仍是演示口令 `Passw0rd!2026`，在公网环境属于高风险。
  入口：`http://8.138.34.151/console` → 左下角头像 → 个人资料 → 修改密码。
- 服务器 root 密码已在本轮对话中出现过，建议同样更换，并改为 SSH 密钥登录 + 禁用密码登录。
- 如需 HTTPS：申请域名与证书后，在 `plaza.conf` 增加 443 server 块，并把 `externalUrl` 同步改为 `https://域名`。

## 八、健康检查

```bash
# 公网首页
curl -s -o /dev/null -w "%{http_code}\n" http://8.138.34.151/

# 应用直连
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8092/

# 管理接口门禁：未登录必须 401（返回 200 就说明门禁被绕过了）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1/api/manage/achievements

# 管理代理自身（回环直连，应 200 且返回 JSON）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8093/api/manage/achievements

# 三个服务都应为 active / enabled
systemctl is-active plaza manage nginx; systemctl is-enabled plaza manage nginx

# 最近一次启动后是否有报错（正常应为 0）
START=$(grep -n "Started Application" /opt/plaza/logs/halo.log | tail -1 | cut -d: -f1)
tail -n +$START /opt/plaza/logs/halo.log | grep -c ERROR
```

判断标准：首页 200、详情页有正文、`/console` 能打开登录页、`/api/manage/` 匿名 401（登录后 200）、启动后 ERROR 数为 0。

---

# 十、v3 版本变更（2026-11-06 00:22 上线）

## 新增内容

| 项 | 说明 |
|---|---|
| `halo.jar` | 重新打包，内含控制台编辑器补丁（DefaultEditor 增加「结构化信息」区块：作品说明 / 项目信息 / 体验方式 / 参考资料），校验标记 `buildRaw` |
| `workdir/themes/theme-earth/templates` | 新增 16 个模板：`docs.html`、`doc.html`、`doc-catalog.html`、`links.html`、`moments.html`、`moment.html`、`photos.html` 等 |
| `workdir/static/favicon.ico` | 站点图标 |
| `workdir/attachments` | 新增上传的封面图及缩略图（w400/w1200/w1600） |
| `/opt/plaza/gateway` | 新增「广场统一网关」服务（IF-08 只读接口 / IF-07 预留），Python 纯标准库 |
| `/etc/systemd/system/gateway.service` | 网关服务单元，限 `127.0.0.1:8094` |

## 网关服务

```bash
systemctl status gateway          # 状态
journalctl -u gateway -n 50       # 日志（[gw] 前缀）
cat /opt/plaza/config/gateway.env # 环境变量（600 权限，含内部签名密钥）
```

- 只绑定 `127.0.0.1:8094`，公网经 Nginx 反代
  （`/api/v1/internal/` 服务态 + `/api/v1/user/` 用户态，同一进程承载）
- 环境变量：`PLAZA_GW_HOST`、`PLAZA_GW_PORT`、`PLAZA_GW_INTERNAL_SIGN_SECRET`
- 调用需 AppKey + HMAC 签名，无签名请求返回 401/403（符合预期）

### 用户态功能联动（X-Internal-Sign）

网关转发用户态请求时会注入 `X-User-Id` / `X-User-Role` / `X-Token-Exp` / … /
`X-Internal-Sign`，广场业务服务（`/api/v1/user/**`）校验内部签名后才执行业务。
两侧共享密钥的解析优先级为：

1. 环境变量 `PLAZA_GW_INTERNAL_SIGN_SECRET`（生产推荐，由 `gateway.env` 注入，见 §4）；
2. 工作目录 `gateway/configs/secrets.json` 的 `internal_sign.secret`（本地/离线联调）；
3. 演示兜底值（仅离线验收，**生产禁用**）。

部署脚本会在首次安装时用 `openssl rand -hex 32` 生成密钥写入
`/opt/plaza/config/gateway.env`（600 权限）；若需与网关侧对齐为同一值，直接替换
该文件中的 `PLAZA_GW_INTERNAL_SIGN_SECRET` 后 `systemctl restart gateway`。
启动日志会打印密钥来源（`env` / `file` / `demo`），排障时可用
`journalctl -u gateway -n 5` 确认。

### v5 增量部署（2026-11-06 12:14，公网 8.138.34.151）

本轮把「用户态功能联动」完整落到服务器并实测打通，覆盖项：

| 项 | 内容 |
|---|---|
| gateway 代码升级 | `server.py`（新增 `/api/v1/user/**` 用户态路由 + 内部签名校验）、`config.py`（密钥统一解析 `env > secrets.json > demo`）、新增 `identity_injector.py`（注入方）、`gateway_config.yaml` 补 `internal.sign` 说明 |
| 密钥对齐 | `/opt/plaza/config/gateway.env` 的 `PLAZA_GW_INTERNAL_SIGN_SECRET` 从随机生成值改为与网关注入方一致的约定共享密钥（备份见 `/opt/plaza/config/gateway.env.bak-*`），重启后启动日志密钥来源显示 `env` |
| Nginx 用户态入口 | `plaza.conf` 新增 `location /api/v1/user/` → `127.0.0.1:8094`（此前公网访问会落到 `location /` 打到 Halo，拿不到 40303 语义） |
| 限流缺陷修正 | `RateLimiter` 由「固定最小间隔」改为真正的**令牌桶**（容量=qps，允许突发），修复同一页面毫秒级并发被误判 429 的问题 |
| 验收 | `scripts/verify_gateway.py` **35 条全绿**（服务态 17 + 用户态 7 + 联动 4 + 预留/工具/IF-07/出站 7）；公网侧首页 200、`/console` 302、`/api/manage` 401、`/api/v1/internal` 401、`/api/v1/user` 403-40303、`/api/unified-login` 401 链路均通 |

回滚：`rm -rf /opt/plaza/gateway && cp -a /opt/plaza/backup/gw-20261106121207/gateway /opt/plaza/gateway && cp -a /opt/plaza/backup/gw-20261106121207/gateway.env /opt/plaza/config/gateway.env && cp -a /opt/plaza/backup/gw-20261106121207/plaza.conf /etc/nginx/conf.d/plaza.conf && systemctl restart gateway && systemctl reload nginx`

## 本次覆盖范围（数据库未动）

- 覆盖：`halo.jar`、`workdir/{themes,static,templates,attachments,plugins/disabled.txt}`、新增 `gateway/`
- 保留：`workdir/db`（线上数据）、`config/`、`manage/`
- 备份：`/opt/plaza/backup/halo.jar.prev-20261106002131`、`themes-20261106002131`、`halo-next.mv.db.before-v3`
- 回滚：`mv /opt/plaza/backup/halo.jar.prev-20261106002131 /opt/plaza/halo.jar && systemctl restart plaza`

## 已知问题：后台文章编辑器打不开

**现象**：`/console/posts/editor?name=<名称>` 弹出「未找到符合 markdown 格式的编辑器，请检查是否已安装编辑器插件」。

**原因**：所有文章 `rawType=markdown`，但服务器 10 个插件里**没有 markdown 编辑器插件**（本地开发实例情况完全相同，属项目既有缺陷，非本次部署引入）。

**修复选项**：

1. **装 Halo 官方 Markdown 编辑器插件**（推荐、低风险）——装完即可正常编辑现有 6 篇文章。
2. 把文章改为 `rawType=html` 以便使用结构化表单 —— **不要直接改**：现有正文的章节名是「技术方案与实现」，而结构化表单只认「作品说明 / 作品内容 / 项目信息 / 体验方式 / 参考资料」，保存时会丢掉「技术方案与实现」整段内容。必须先重构正文结构。

**注**：结构化表单补丁本身已生效（`buildRaw` 可在控制台 UI 资源里查到），但要它出现在界面上，文章必须是 `rawType=html`。

## 新增页面模板为何 404

`/docs`、`/links`、`/moments`、`/photos` 返回 404 是**预期**：这些是「单页」模板，需要在后台「页面」里新建对应 slug 的页面并选择模板后才会生效。线上当前只有 3 个单页（`about`、`privacy-policy`、`user-agreement`），本地也一样。

---

# 十一、v4 版本变更（2026-11-06 09:25 上线，增量）

本轮先做**全量指纹比对**（jar / themes / templates / static / attachments 的 md5 清单），确认这些与线上完全一致，因此只增量推送 3 个真正有差异的文件，未重传 121MB 主程序。

| 文件 | 变化 | 影响 |
|---|---|---|
| `/opt/plaza/manage/manage_server.py` | 新增 `check_admin()` 角色校验（把调用者 Cookie 转给 Halo `users/-/permissions`，无 `*` 或 `system:posts:manage` 即 403） | **安全修复**：此前线上代理未校验角色，任何登录用户都能调 `/api/manage` 改删成果 |
| `/opt/plaza/gateway/account_verify.py` | 新增（广场对接警院论坛「账号确认接口」的调用封装，L2 签名复用 `sign.py`） | 仅新增能力，未被 `server.py` 引用，不影响现有 IF-08 |
| `/opt/plaza/gateway/gateway_config.yaml` | 新增 `plaza.account.verify.*` 配置段 | 供 account_verify 使用 |

- 备份：`/opt/plaza/backup/manage_server.py.prev-20261106092347`、`gateway_config.yaml.prev-20261106092347`
- 重启：`systemctl restart manage gateway`（Halo 与 Nginx 未变动，无需重启/reload）
- 验收：首页 200（78KB/0.07s）、`/console` 302→`/login?authentication_required`、匿名 `/api/manage` 401、admin 登录后 GET 列表 200（6 条）、admin PUT 探测 404（已过权限校验）、网关无签名 40105、启动后 ERROR 数 0

## 环境陷阱：服务器有两套 Python

`python3` 是系统自带的 **3.6.8**，`from __future__ import annotations` 在 3.6 上直接 SyntaxError；而两个服务用的是 `/usr/bin/python3.11`。
**做语法检查必须用 `python3.11 -m py_compile`，不要用 `python3`**，否则会误判成代码错误。

## 已知差异：线上没有普通用户账号

线上用户只有 `admin`（超级管理员）、`anonymousUser`、`ghost`。本机演示用的 `student`（角色 `post-author`）**未在线上创建**，因此「普通用户看不到编辑/删除按钮」这条只能由权限接口层验证（匿名 401、越权 403 均已通过），无法用账号实测。
如需补建，在 `/console` → 用户 → 新建，角色选「作者」，然后即可复测。

---

# 十二、v5 版本变更（2026-11-06 10:13 上线）：统一身份登录

## 新增了什么

| 组件 | 位置 | 说明 |
|---|---|---|
| 统一登录 BFF | `/opt/plaza/gateway/{login_server.py,unified_login.py}` | 论坛账号确认 → Halo 本地用户映射/创建 → 角色映射；纯标准库 |
| BFF 服务 | `/etc/systemd/system/login.service` | 监听 **127.0.0.1:8095**，`Restart=always`，开机自启 |
| BFF 环境变量 | `/opt/plaza/config/login.env`（600） | 端口、Origin 白名单、Halo 管理凭据 |
| 论坛 AppSecret | `/opt/plaza/gateway/configs/secrets.json`（600） | `account_verify` 读取；环境变量优先于该文件 |
| 登录页模板 | `workdir/templates/gateway_fragments/{login.html,common.html}` | 默认「统一身份登录」，可一键切回本地账号 |

## 端口策略（重要，别照搬 8095 暴露方案）

**只对外开 80**，不开放 8095：

```
浏览器 http://8.138.34.151/login
   │  前端 bffUrl()：页面在 80/443 → 同源 /api/unified-login
   ▼
Nginx  location = /api/unified-login  →  proxy_pass 127.0.0.1:8095
   ▼
BFF（只绑回环，公网直连 8095 不可达）
```

因此**不需要改阿里云安全组、不需要额外放行端口**。本地开发实例（8092）没有 Nginx，前端会自动降级为 `hostname:8095` 直连，行为不变。

## 本地代码适配点（与线上同步）

`common.html` 的 `bffUrl()` 改为端口判定：`""/80/443 → location.origin + "/api/unified-login"`；其它端口 → `hostname:8095`。
以后若把站点点到域名 + 443，无需再改前端。

## 验收结果（线上实测）

| 项 | 结果 |
|---|---|
| 首页 / 登录页 | `200` / `200`（17.5KB） |
| 登录页默认态 | 提示「请使用警院论坛（WeChat 五平台）账号登录，首次登录将自动开通本站账号并同步角色权限」；存在「使用本地账号登录」兜底入口，点击后文案互切正常 |
| 前端 JS | 无 pageerror（唯一 console error 是探测请求返回的 401，属预期） |
| 公网 `POST /api/unified-login` | `401 {"reason":"invalid_credentials"}`（链路通） |
| BFF 真实链路 | `verify_account` 返回 `confirmed=False, reason=invalid_credentials, request_id=04e5493b-…` → **签名通过、网关可达、业务正常拒绝** |
| 公网直连 `:8095` | 不可达（预期，仅回环） |
| 服务状态 | `plaza/login/manage/gateway/nginx` 全 active；Halo 重启后 ERROR 数 0 |

## 坑：论坛账号确认接口要求邮箱格式

用非邮箱账号（如 `probe_not_exist`）调用，论坛返回 **`invalid_params`**，不是 `invalid_credentials`；换成 `xxx@example.com` 才返回 `invalid_credentials` 并带 `request_id`。
登录页提示里已引导「用户名或邮箱地址」，但排查时注意这两种 reason 的区别——`invalid_params` 通常是账号格式问题，而不是密钥或签名问题。

## 回滚

```bash
systemctl stop login && systemctl disable login
cp /opt/plaza/backup/v5-20261106101500/plaza.conf /etc/nginx/conf.d/plaza.conf
cp /opt/plaza/backup/v5-20261106101500/common.html /opt/plaza/workdir/templates/gateway_fragments/
cp /opt/plaza/backup/v5-20261106101500/login.html /opt/plaza/workdir/templates/gateway_fragments/
cp /opt/plaza/backup/v5-20261106101500/account_verify.py /opt/plaza/gateway/
rm -f /etc/systemd/system/login.service && systemctl daemon-reload
systemctl reload nginx && systemctl restart plaza
```


