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
