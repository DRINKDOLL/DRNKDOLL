# 项目长期约定（精编版）

## 1. 启动 / 运行广场（用户说「运行/启动/打开广场」即执行）

- 路径：`C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn`，端口 8092，首页 http://127.0.0.1:8092/ ，后台 /console。
- 用 `run_in_background: true` 启动，**java.exe 与 jar 必须绝对路径**（相对路径在后台任务里会 127 退出）；不要重定向 stdout（让 logback 写 `run/halo.log`）：

```
cd "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn" && source ./env.sh && \
env -u SERVER__PORT -u SERVER__HOST -u SERVER_PORT -u SERVER_ADDRESS \
  NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
  "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-lab/tools/jdk-21.0.13.0.2+1/bin/java.exe" \
  -Xms256m -Xmx512m -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 -Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai \
  -jar "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-lab/jars/halo-2.27.2.jar" \
  --spring.config.additional-location=file:./config/ --server.port=8092 --server.address=0.0.0.0
```

- 排障：`run/halo.log` 只到「Finished Spring Data repository scanning」而无「Starting R2DBC migration」= 进程在连 H2 前就死了（`Start-Process -WindowStyle Hidden` 必现，别用）。子进程 PID ≠ 任务 PID，用 `tasklist | grep java` + `netstat -ano | grep :8092` 确认真实监听。后台任务退出码 127/1073807364 不代表真失败，先 `curl` 首页 + 查进程再判断。
- **沙箱会回收会话内启动的后台进程**，稳定常驻靠 Windows 计划任务「警院成果广场自启动」（AtLogOn，执行 `halo-cn/autostart_task.bat`，该脚本同时拉起 Halo 8092 与登录 BFF 8095）。手动验证 `Start-ScheduledTask -TaskName "警院成果广场自启动"`。
- 自启动脚本要点：绝对路径写死 java/jar/workdir；**bat 必须 GBK + CRLF**（`iconv -f UTF-8 -t GBK 源 | sed 's/$/\r/' > 目标.bat`，不要用 Write 工具写 bat）；注释全用 ASCII；清代理并设 `NO_PROXY=127.0.0.1,localhost,::1`；开头用 `netstat|findstr :8092|findstr LISTENING` 防重复启动。三处需同步：Startup bat、`autostart_task.bat`、计划任务动作。
- 登录凭据（每次「运行」都要一并清晰列出）：
  - 管理员 admin / Passw0rd!2026（可进 /console）
  - 普通用户 student / Student!2026（post-author，跳 /uc，不能进后台）
- 启动后轮询首页到 HTTP 200，再 `present_files` 打开。端口占用/H2 被锁（MVStoreException）先确保 8092 释放。

## 2. 定制 Halo 界面的三条通道

- **主题模板** `workdir/themes/theme-earth/templates/**`：改完必须重启（Thymeleaf 缓存）。
- **核心模板**（登录/注册/错误页）：需在 `config/application.yaml` 配 `spring.thymeleaf.prefix: file:./workdir/templates/` 才生效；模板来自 `jar xf ... BOOT-INF/classes/templates` 全量提取（含 `*.properties`，缺了丢中文）。登录页站名在 `gateway_fragments/common.html` 的 `haloLogo`，背景在 `gateway_fragments/layout.html` 的 `<body class="gateway-page">`。改内联样式最稳（HTML 响应 no-cache）。
- **核心静态资源** `workdir/static/**` 覆盖 jar，改完无需重启；但有 1 年 max-age 且 URL 固定 `?v=2.27.2`，用户浏览器缓存后看不到改动（需 Ctrl+Shift+R）→ 视觉改动优先走模板通道，别依赖静态替换。
- theme-earth 是预编译主题，`text-4xl`/`font-bold`/`md:grid-cols-3` 等类**不在 CSS 里**，改类名无效；用内联 style 或已编译类（`lg:grid-cols-3`、`cursor-pointer`）。
- `bootstrap.sh` 校验 jar sha256（`start.sh` 不校验），不重跑 bootstrap 时改 jar 是最后手段（先 `cp` 备份）。

## 3. 文章正文为空 = 快照缺渲染产物

- 现象：详情页只有标题、正文空白。查 `GET /apis/api.console.halo.run/v1alpha1/posts/{name}/head-content`，`raw` 有内容而 `content` 为 0 字节即此症。原因：Halo 由**前端**把 markdown 编译成 HTML 再提交。
- 修复：`PUT .../posts/{name}/content`（body `{raw,content,rawType:"markdown"}`）→ `PUT .../{name}/publish`（必须 PUT，POST 404）。现成脚本 `halo-cn/scripts/render_post_content.py`（`--dry-run/--post NAME/--force`）。
- PostEndpoint 是 RouterFunction，只有：`posts`、`posts/{name}`、`posts/{name}/content`、`/release-content`、`/head-content`、`/snapshot`、`/revert-content`、`/publish`、`/unpublish`、`/recycle`；`/draft` 与 GET `posts/{name}` 都 404。

## 4. 成果详情爬虫

- `scripts/crawl_achievements.py` + `scripts/achievement_sources.json`（slug→url/selector/summary/max_chars/max_images），纯标准库（urllib + html.parser），`--dry-run/--slug/--no-images/--prune-images`。
- 流程：取正文容器（`tag.cls`/`#id`/`.cls`，为空或过少用 `auto_content` 兜底）→ 白名单抽块（h2-h4/p/ul/ol/table/figure/img/blockquote）→ `SECTION_SKIP` 丢安装/依赖/FAQ/许可类 → `polish()` → 图片下载改写 → 写库发布。
- 可访问性：维基/百度百科抓不到；阿里云开发者社区前端渲染抓不到；腾讯云开发者社区最稳。
- 坑：`SKIP_CLASS_HINTS` 用精确 token（曾用 `mark` 误杀 `rno-markdown`）；`pre` 被主题 blur 直接跳过；图片 URL 要 `quote()`。
- 图片落 `workdir/static/images/achievements/<slug>/`，站内 `/images/achievements/...`，无需重启。正文固定结构：作品说明/技术方案与实现/项目信息/体验方式/参考资料。暗色下需在 main CSS 追加 `.dark #content ...` 覆盖。

## 5. 卡片 / 详情页（改卡片必须两边都改）

- 服务端 `modules/post-card.html`（+`featured-post-card.html`）被 index/category/author/tag 复用；**`archives.html` 有独立列表结构，需单独改**。
- 客户端 `index.html` 与 `category.html` **各有一份 `renderCard`**：只改模板则切分类后新元素消失，只改 JS 则首屏没有。
- 卡片简介已是详情页链接（`<a>` 包 `th:text`）；标题下另有胶囊「查看项目详情 ›」（`.post-detail-link`），hover 样式在 `templates/assets/main-BaWd_1hx.css` 末尾，需 `!important`。
- 返回入口：`post.html` 顶部/底部各一 `a[data-post-back]`（文案 `[data-post-back-label]`），`</body>` 前脚本处理：同源 referrer → 目标为 referrer、文案「返回上一页」，点击先 `history.back()`，400ms 未离开再 `location.assign`；无 referrer → `/`、「返回首页」。首页分类筛选状态写在 `#cat=<分类名>` hash，否则返回丢状态。
- 公开接口（免鉴权）：`GET /apis/api.content.halo.run/v1alpha1/posts/{name}` 返回 `content:{raw,content}`；列表 `.../posts`、`.../categories/{name}/posts`。

## 6. 控制台 / 个人中心（SPA）定制

- 映射硬编码在 `WebFluxConfig`，workdir 无法覆盖：`/console`→jar `BOOT-INF/classes/ui/console.html`（no-store，刷新即生效）、`/uc`→`uc.html`、`/ui-assets/**`→classpath；只有 `/**` 走 workdir/static 且优先级更低。
- 侧边栏「Halo」标志是**内联 SVG**（`.sidebar__logo`），只能改 jar 内 console.html。已在唯一 `<style>` 块追加：
  ```css
  .sidebar__logo{display:none!important}
  .sidebar__logo-container a::after{content:"警院成果展示广场";display:block;font-size:1.0625rem;font-weight:700;color:#0e1731;letter-spacing:.02em;white-space:nowrap;line-height:2rem}
  ```
- 改 jar 姿势：停实例 → `jar uf <jar> BOOT-INF/classes/ui/console.html <同目录 .gz>`（.gz 用 `gzip.compress(data,9,mtime=0)`）→ 启动。备份 `halo-lab/jars/halo-2.27.2.jar.bak-20261104`。
- 控制台 SPA 持续轮询，Playwright 用 `networkidle` 会超时，改 `domcontentloaded` + 固定等待。

## 7. 统一身份登录（论坛账号 → 广场会话）

- 组成：`gateway/unified_login.py`（链路）+ `gateway/login_server.py`（BFF，端口 **8095**，纯标准库）+ 登录页前端。
- 链路：登录页拦提交 → BFF `POST /api/unified-login` 做论坛确认 → `forum-<user_id>` 映射本地用户（幂等）→ 前端换 username、密码不变 → 原生 `POST /login` 由 Spring Security 建会话。BFF **不代建会话**。
- 每次登录：已存在用户同步密码（`PUT /apis/api.console.halo.run/v1alpha1/users/{name}/password`，body `{password}`，admin 令牌即可）+ 尽力 grant 角色（Halo 只支持追加，**降权需控制台手工处理**，已知限制）。
- 角色映射：admin→super-role，teacher/assistant→post-author，student/其他→guest。
- 启动 BFF：`python -m gateway.login_server`（系统 python 绝对路径 `C:/Users/LENOVO/AppData/Local/Programs/Python/Python313-32/python.exe`），已并入 `autostart_task.bat`（Halo 8092 + BFF 8095）。
- **前端坑**：submit 事件处理里调 `form.requestSubmit()` 会被浏览器静默忽略（点了没反应、无报错），必须用 `form.submit()`。
- BFF Origin 校验：白名单命中 **或** 与请求 `Host` 同主机不同端口（否则局域网 IP 访问一律 403）。
- 登录卡片是白底，提示文字用深色（`#4b5563`/`#0e1731`），浅色会看不见；兜底入口「使用本地账号登录」用于 admin/student 本地账号与 BFF 未启动降级。
- 验收脚本 `scripts/verify_unified_login.js`（Playwright，10 项断言）。说明文档 `gateway/README-unified-login.md`。

## 7.1 网关接入（服务态 8094 / 用户态入站）

- **入站**两种鉴权模型，都在 `gateway/server.py`（8094）：
  - 服务态 `/api/v1/internal/**`：消费方 AppKey + L2 签名（`X-App-Key`+HMAC-SHA256），只读、白名单默认拒绝、限流。
  - 用户态 `/api/v1/user/**`：由**网关**注入 `X-User-Id`/`X-User-Role`/`X-Token-Exp`/`X-Internal-Sign` 等；广场校验内部签名（缺失/伪造 → **403/40303**）、令牌过期（**401/40103**）、水平越权（非作者非管理员 **403/70002**，管理员豁免）。接线 `identity.parse_identity`+`enforce_owner`。
- **功能联动**（注入方→校验方闭环）：注入方 `gateway/identity_injector.py`（`build_identity_headers`/`call_user_api`/CLI），校验方 `identity.py`+`/api/v1/user/**`。内部签名密钥**统一解析** `config.resolve_internal_sign_secret()`：env `PLAZA_GW_INTERNAL_SIGN_SECRET` > `configs/secrets.json` 的 `internal_sign.secret`（已 gitignore）> demo 兜底；`internal_sign_secret_source()` 返回来源，启动日志会打印。**注入方/校验方/验收脚本三处必须同一解析，否则联动整体 403。** CLI 有 MSYS 路径改写防御（Git Bash 会把 `/api/...` 改成 `C:/Program Files/Git/api/...`）。
- **出站**：`gateway/account_verify.py` 走真实外网 `POST http://8.138.246.181/answer/api/v1/account/verify`（L2 签名），正向 200/uid=1、反向 401/40104 防枚举。
- **验收**：`scripts/verify_gateway.py` **35 条**（服务态 17 + 用户态入站 7 + **功能联动 4** + 工具 2 + IF-07 降级 1 + 出站桩 4/实际 2）全绿，可复跑。文档 `gateway/README-gateway-status.md`（含「功能联动」章节、90 天轮换、已知限制）。
- 三要素结论：入站严格验签（伪造 403）/ 出站 L2+confirmed / 上游桩→真实 BFF，均已完成实测。
- 密钥轮换：`svc-plaza` 90 天（S1 核心），其余季度自查；**历史密钥经截图分发过，首次轮换须一并作废**。
- **限流**：`server.py` 的 `RateLimiter` 是**令牌桶**（容量=qps=100，允许突发，长期均值限 100 QPS）。勿改回「固定最小间隔」——那会把同页并发请求误判 429。

## 7.2 公网服务器部署（8.138.34.151）

- 服务器：阿里云轻量应用服务器（SWAS，**不是 ECS**）；Alibaba Cloud Linux 3 / x86_64 / 2C1.8G；Python 3.11、JDK 21。四服务 systemd 单元全 `enabled` 常驻：`plaza`(8092)、`manage`(8093)、`gateway`(8094)、`nginx`(80)。均开自启。
- 目录：`/opt/plaza/{halo.jar,config,workdir,gateway,manage,scripts,backup,logs}`；配置 `config/{application.yaml,gateway.env,manage.env}`（600）、`configs/secrets.json`。
- 部署通道：`deploy/dpl.py`（paramiko）+ `deploy/deploy_now.sh`；凭据从环境变量读：`DPL_HOST=8.138.34.151 DPL_USER=root DPL_KEY=deploy/ssh/deploy_ed25519`（服务器已禁密码登录，**密钥登录仍有效**）。paramiko 只在 WorkBuddy 自带 Python 里：`C:/Users/LENOVO/.workbuddy/binaries/python/versions/3.13.12/python.exe`。
- **Git Bash 必设 `MSYS2_ARG_CONV_EXCL="*"`**：否则 `dpl.py put <local> /opt/...` 的远端绝对路径被改写成 `C:/Program Files/Git/opt/...`，SFTP 报 `FileNotFoundError`。
- Nginx `deploy/plaza.conf`：`/api/manage/`→8093（`auth_request /_manage_authz` 门禁）、`= /api/unified-login`→8095、`/api/v1/internal/`→8094、**`/api/v1/user/`→8094**、`/`→8092。改完 `nginx -t && systemctl reload nginx`。
- `gateway.env` 的 `PLAZA_GW_INTERNAL_SIGN_SECRET` 部署脚本首次会**随机生成**；若要与网关侧一致须手工替换为约定共享值后 `systemctl restart gateway`。密钥来源看启动日志（env/file/demo）。
- v5（2026-11-06 12:14）：升级 gateway（用户态路由+注入器）、对齐密钥、补 Nginx 用户态入口、修限流令牌桶。备份 `/opt/plaza/backup/gw-20261106121207/`。README-DEPLOY 有「v5 增量部署」+回滚命令。

## 7.3 账号管理（用户/角色）

- **账号与角色是运行时数据**（`workdir/db/halo-next.mv.db`，已 gitignore），git 无法复现；用可版本化脚本固化操作：`halo-cn/scripts/grant_admin.py <username>`（幂等：不存在则建号、存在则保留密码、追加 super-role、末校验）。可传 `--password` / `--roles a,b` / `--reset-password`。
- 授权接口：`POST /apis/api.console.halo.run/v1alpha1/users/{name}/permissions`，body `{"roles":["super-role"]}`（**追加语义**，Halo 不支持降权，需控制台手工处理）。创建：`POST /apis/api.console.halo.run/v1alpha1/users`（body `name/displayName/email/password`，创建接口默认给 guest，须再 grant）。改密：`PUT .../users/{name}/password` body `{"password":...}`。
- **删/禁用用户不在 `/apis/...` 下**（一律 404）：控制台 SPA 用的是 `DELETE /api/v1alpha1/users/{name}`；disable/enable 为 `/api/v1alpha1/users/{username}/disable|enable`。
- 角色映射（`gateway/unified_login.py` ROLE_MAP）：admin→super-role；teacher/assistant→post-author；student/其他→guest。
- 单用户读取返回 `{"user":{...},"roles":[...]}`；列表接口 `items[]` 直接是 User。
- **已知遗留安全债**：`deploy/ssh/deploy_ed25519`、`workdir/keys/pat_id_rsa`、`deploy/{manage,login}.env` 曾进入提交 `5153595` 与远端，虽已 `git rm --cached` + gitignore，但**历史仍含明文**，须 filter-repo/BFG 清史并轮换 SSH 密钥/PAT。

## 8. 其他工程约定

- 全程只用 Python 标准库，不引入文档外技术。
- Python：`base64.b64encode(b'...')` 已是 bytes；子进程 `python -c` 需 `export PYTHONPATH=<halo-cn>` 才能 import gateway。
- bash 里中文 `curl -d` 会乱码，改用 Python json 编码。
- 后台服务一律用 Bash `run_in_background:true`。
- 工作日志追加在 `.workbuddy/memory/YYYY-MM-DD.md`。
- **推送 GitHub**：会话注入代理对 `github.com` 的 CONNECT 隧道**频繁 502**（`api.github.com` 较稳），单次成功率约 1/5 → 用循环 `for i in $(seq 1 8); do git push origin main && break; sleep 4; done`。仓库 `https://github.com/DRINKDOLL/DRNKDOLL` 分支 `main`，凭据已存 Windows 凭据管理器（DRINKDOLL + gho_ 令牌）。
- **入库排除**（`.gitignore`）：`*.env`、`ssh/`、`workdir/keys/`、`gateway/configs/secrets.json`、`deploy/pkg3/`(134M jar)、`halo-lab/tools|jars|work`、插件 jar、`workdir/db|indices|attachments|archive`、演示工具 `.cache/.slidep`、`__pycache__/`、`halo-cn/output/`（文档流水线产物）、抓取临时 `deploy/{loc,rem}.html`。
