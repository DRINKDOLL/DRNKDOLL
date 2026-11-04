# 警院成果展示广场 —— 服务器部署说明

**访问地址**：http://8.138.34.151/
**管理后台**：http://8.138.34.151/console

## 一、架构

```
公网 :80  ──►  Nginx（反代 + WebSocket 透传）  ──►  Halo 2.27.2  127.0.0.1:8092
                                                        │
                                                        └── H2 数据库 + workdir
```

- Nginx 监听 80（同时是默认虚拟主机，覆盖系统欢迎页）
- Halo 只绑定回环地址 `127.0.0.1:8092`，不直接对外暴露
- 运行环境：Alibaba Cloud Linux 3 / x86_64 / 2C1.8G，JDK 21.0.13（Temurin）

## 二、目录与文件

| 路径 | 说明 |
|---|---|
| `/opt/jdk21/` | JDK 21 运行时（独立安装，不污染系统包） |
| `/opt/plaza/halo.jar` | Halo 2.27.2 主程序 |
| `/opt/plaza/config/application.yaml` | 站点配置（端口、工作目录、模板路径、日志） |
| `/opt/plaza/workdir/` | 数据目录：`db/` 数据库、`static/` 站内图片、`themes/` 主题、`templates/` 定制模板、`plugins/` 插件 |
| `/opt/plaza/logs/halo.log` | 应用日志（滚动） |
| `/opt/plaza/backup/` | 数据库备份 |
| `/etc/systemd/system/plaza.service` | 服务单元（开机自启、异常自动重启） |
| `/etc/nginx/conf.d/plaza.conf` | 反向代理配置 |
| `/var/log/nginx/plaza.access.log` | 访问日志 |

## 三、常用运维命令

```bash
systemctl status plaza          # 查看应用状态
systemctl restart plaza         # 重启应用（改配置后必须重启）
journalctl -u plaza -n 100      # 若标准输出异常，看这里
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

3. **HTTP Basic 认证**
   `halo.security.basic-auth.disabled: true` 已生效：匿名访问受保护接口会被 302 跳转到登录页，无法用账号密码直接调管理接口。
   若日后需要用脚本调 API，把它改为 `false` 并重启；用完后务必改回。

## 六、安全建议

- **立即修改管理员密码**：当前仍是演示口令 `Passw0rd!2026`，在公网环境属于高风险。
  入口：`http://8.138.34.151/console` → 左下角头像 → 个人资料 → 修改密码。
- 服务器 root 密码已在本轮对话中出现过，建议同样更换，并改为 SSH 密钥登录 + 禁用密码登录。
- 如需 HTTPS：申请域名与证书后，在 `plaza.conf` 增加 443 server 块，并把 `externalUrl` 同步改为 `https://域名`。

## 七、健康检查

```bash
# 公网首页
curl -s -o /dev/null -w "%{http_code}\n" http://8.138.34.151/

# 应用直连
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8092/

# 最近一次启动后是否有报错（正常应为 0）
START=$(grep -n "Started Application" /opt/plaza/logs/halo.log | tail -1 | cut -d: -f1)
tail -n +$START /opt/plaza/logs/halo.log | grep -c ERROR
```

判断标准：首页 200、详情页有正文、`/console` 能打开登录页、启动后 ERROR 数为 0。
