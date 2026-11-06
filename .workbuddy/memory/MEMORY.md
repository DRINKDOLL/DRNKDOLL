# 项目长期约定（精编）

## 1. 运行广场
- 路径 `output/plaza-20261103/halo-cn`，端口 8092，首页 http://127.0.0.1:8092/ ，后台 /console。
- 启动用 `run_in_background:true` + java/jar **绝对路径**（相对路径后台任务 127 退出）；勿重定向 stdout（logback 写 `run/halo.log`）：
  `cd <halo-cn> && source ./env.sh && env -u SERVER__PORT -u SERVER__HOST -u SERVER_PORT -u SERVER_ADDRESS NO_PROXY=127.0.0.1,localhost <jdk21>/bin/java.exe -Xms256m -Xmx512m -Dfile.encoding=UTF-8 -Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai -jar <halo-2.27.2.jar> --spring.config.additional-location=file:./config/ --server.port=8092 --server.address=0.0.0.0`
- 排障：log 停在 repository scanning = 连 H2 前就死（`Start-Process -WindowStyle Hidden` 必现）；子进程 PID≠任务 PID，用 `tasklist`+`netstat -ano|grep :8092` 确认；退出码 127/1073807364 不代表真失败，先 curl 首页。
- 稳定常驻靠 Windows 计划任务「警院成果广场自启动」（AtLogOn → `halo-cn/autostart_task.bat`，同时拉起 Halo 8092 + 登录 BFF 8095）。bat 必须 GBK+CRLF（`iconv -f UTF-8 -t GBK | sed 's/$/\r/'`），注释全 ASCII，三处同步。
- 凭据：admin/Passw0rd!2026（进 /console）；student/Student!2026（post-author，跳 /uc）。

## 2. 改 Halo 界面三条通道
- 主题模板 `workdir/themes/theme-earth/templates/**`：改完**重启**（Thymeleaf 缓存）。
- 核心模板（登录/注册/错误页）：需 `config/application.yaml` 配 `spring.thymeleaf.prefix: file:./workdir/templates/`；提取自 jar `BOOT-INF/classes/templates`（含 *.properties 否则丢中文）。`gateway_fragments/common.html` 的 haloLogo=站名，`layout.html` body.gateway-page=背景。内联样式最稳。
- 核心静态 `workdir/static/**` 覆盖 jar、免重启；但 1 年 max-age + URL 固定，需 Ctrl+Shift+R → 视觉改动优先走模板。
- theme-earth 是**预编译**主题，`text-4xl`/`font-bold`/`md:*` 不在 CSS，改类名无效；用内联 style 或已编译类（`lg:grid-cols-3`）。
- `/console`→jar `BOOT-INF/classes/ui/console.html`（no-store，刷新即生效）、`/uc`→uc.html、`/ui-assets/**`→classpath（映射硬编码在 WebFluxConfig，workdir 无法覆盖）。侧边栏 logo 是内联 SVG `.sidebar__logo`，只能改 jar 内 console.html（已在 `<style>` 块追加隐藏 + `::after` 改名「警院成果展示广场」）。
- 改 jar：停实例 → `jar uf <jar> BOOT-INF/classes/ui/console.html <同目录 .gz>`（.gz = `gzip.compress(data,9,mtime=0)`）→ 启动。备份 `halo-lab/jars/halo-2.27.2.jar.bak-20261104`。
- 控制台 SPA 持续轮询，Playwright 用 `domcontentloaded`+固定等待，勿用 networkidle。

## 3. 文章正文为空 = 快照缺渲染产物
- 判据：`GET /apis/api.console.halo.run/v1alpha1/posts/{name}/head-content`，raw 有内容而 content 0 字节。
- 修复：`PUT .../posts/{name}/content`（{raw,content,rawType:"markdown"}）→ `PUT .../{name}/publish`（必须 PUT）。脚本 `halo-cn/scripts/render_post_content.py`。
- PostEndpoint（RouterFunction）只有 posts、posts/{name}、/content、/release-content、/head-content、/snapshot、/revert-content、/publish、/unpublish、/recycle；`/draft` 与 GET posts/{name} 都 404。

## 4. 成果爬虫
- `scripts/crawl_achievements.py`+`achievement_sources.json`（slug→url/selector/summary/max_chars/max_images），纯标准库，`--dry-run/--slug/--no-images/--prune-images`。
- 容器→白名单块（h2-h4/p/ul/ol/table/figure/img/blockquote）→SECTION_SKIP 丢安装/依赖/FAQ→polish→图片改写→发布。腾讯云社区最稳；维基/百科/阿里云抓不到。坑：`pre` 被主题 blur 跳过；图片 URL 要 `quote()`；`SKIP_CLASS_HINTS` 用精确 token。
- 图片落 `workdir/static/images/achievements/<slug>/`，站内 `/images/achievements/...`，免重启。

## 5. 卡片/详情页（**两边都改**）
- 服务端 `modules/post-card.html`(+featured-) 被 index/category/author/tag 复用；`archives.html` 独立结构。
- 客户端 `index.html` 与 `category.html` **各有一份 `renderCard`**。
- 返回入口 `post.html` 顶部/底部 `a[data-post-back]`，`</body>` 前脚本按 referrer 决定目标；首页分类筛选状态存 `#cat=<分类名>`。
- 公开接口（免鉴权）：`/apis/api.content.halo.run/v1alpha1/posts/{name}` 返回 content{raw,content}；列表 `.../posts`、`.../categories/{name}/posts`。

## 6. 统一身份登录（论坛→广场）
- `gateway/unified_login.py` + `gateway/login_server.py`（BFF 8095，纯标准库）+ 登录页前端。链路：登录页拦提交 → BFF `POST /api/unified-login` 论坛确认 → `forum-<user_id>` 本地用户（幂等）→ 前端换 username、密码不变 → 原生 `POST /login` 建会话。BFF **不代建会话**。
- 角色映射（ROLE_MAP）：admin→super-role；teacher/assistant→post-author；student/其他→guest。
- **登录不降权（2026-11-06 修，重要）**：`POST /apis/api.console.halo.run/v1alpha1/users/{name}/permissions` 是**替换语义**（不是追加！）。原实现每次登录无条件按论坛角色同步 → 手工授的管理员被冲回 guest。现 `sync_role` 按 ROLE_RANK（super 100 > post-author 50 > guest 10）**仅在目标等级 ≥ 现有最高等级时写入**，否则跳过；升权照常自动生效。BFF 响应含 `effective_role`。
- 前端坑：submit 里 `form.requestSubmit()` 被静默忽略，必须 `form.submit()`。BFF Origin 校验：白名单命中**或**同主机不同端口。登录卡片白底 → 提示文字用深色。
- 启动 BFF：`python -m gateway.login_server`（系统 python `C:/Users/LENOVO/AppData/Local/Programs/Python/Python313-32/python.exe`）。验收 `scripts/verify_unified_login.js`（10 断言）。文档 `gateway/README-unified-login.md`。

## 7. 网关接入（8094）
- 入站：服务态 `/api/v1/internal/**`（AppKey + L2 HMAC-SHA256 签名，只读、白名单默认拒绝、限流）；用户态 `/api/v1/user/**`（网关注入 X-User-Id/X-User-Role/X-Token-Exp/X-Internal-Sign，广场校验：缺失/伪造 403/40303、过期 401/40103、越权 403/70002 管理员豁免）。接线 `identity.parse_identity`+`enforce_owner`。
- 功能联动：注入方 `gateway/identity_injector.py`，校验方 `identity.py`。内部签名密钥统一 `config.resolve_internal_sign_secret()`（env `PLAZA_GW_INTERNAL_SIGN_SECRET` > `configs/secrets.json` internal_sign.secret > demo 兜底），**三处必须同一解析**否则整体 403。
- 出站 `gateway/account_verify.py`：真实外网 `POST http://8.138.246.181/answer/api/v1/account/verify`（L2），正向 200、反向 401/40104。
- 验收 `scripts/verify_gateway.py` 35 条全绿。限流是**令牌桶**（容量=qps=100），勿改回固定最小间隔。密钥轮换 `svc-plaza` 90 天。

## 8. 公网部署（8.138.34.151）
- 阿里云轻量应用服务器（SWAS），Alibaba Cloud Linux 3 / 2C1.8G，Py3.11+JDK21。systemd 常驻：plaza(8092)/manage(8093)/gateway(8094)/login(8095)/nginx(80)，全 enabled。目录 `/opt/plaza/{halo.jar,config,workdir,gateway,manage,scripts,backup,logs}`。
- 通道 `deploy/dpl.py`（paramiko）+`deploy_now.sh`：`DPL_HOST=8.138.34.151 DPL_USER=root DPL_KEY=deploy/ssh/deploy_ed25519`，paramiko 只在 WorkBuddy python `C:/Users/LENOVO/.workbuddy/binaries/python/versions/3.13.12/python.exe`。**Git Bash 必设 `MSYS2_ARG_CONV_EXCL="*"`**（否则远端绝对路径被改写）。
- Nginx `deploy/plaza.conf`：`/api/manage/`→8093、`= /api/unified-login`→8095、`/api/v1/internal/`+`/api/v1/user/`→8094、`/`→8092。改完 `nginx -t && systemctl reload nginx`。
- 线上 `fengyukai` 经统一登录映射为本地账号 **`forum-13`**。**本地 8092 ≠ 线上，两套独立数据库**。
- 部署脚本首次随机生成 `PLAZA_GW_INTERNAL_SIGN_SECRET`；要与网关一致须手工替换后 restart gateway。

## 9. 账号/角色管理
- 运行时数据存 `workdir/db/halo-next.mv.db`（gitignore），git 无法复现 → 用 `halo-cn/scripts/grant_admin.py <username>`（幂等：不存在则建、存在保留密码、授 super-role、末校验）。参数 `--password/--roles a,b/--reset-password`。
- 接口：创建 `POST /apis/api.console.halo.run/v1alpha1/users`（默认 guest，须再 grant）；改密 `PUT .../users/{name}/password` {password}；**删/禁用不在 `/apis/...`**：`DELETE /api/v1alpha1/users/{name}`、`/api/v1alpha1/users/{username}/disable|enable`。单用户返回 {user,roles}，列表 items[] 是 User。
- **遗留安全债**：`deploy/ssh/deploy_ed25519`、`workdir/keys/pat_id_rsa`、`deploy/{manage,login}.env` 曾进提交 `5153595` 与远端，已 rm --cached+gitignore，但历史仍含明文 → 须 filter-repo/BFG 清史 + 轮换密钥。

## 10. 工程约定
- 全程只 Python 标准库。`python -c` 需 `export PYTHONPATH=<halo-cn>` 才能 import gateway。bash 中文 `curl -d` 乱码 → 用 Python json。
- 后台服务用 Bash `run_in_background:true`。工作日志追加 `.workbuddy/memory/YYYY-MM-DD.md`。
- 推送 GitHub：会话代理对 `github.com` 频繁 502（api.github.com 较稳），单次成功率 ~1/5 → 循环 `for i in $(seq 1 8); do git push origin main && break; sleep 4; done`。仓库 `https://github.com/DRINKDOLL/DRNKDOLL` 分支 main。
- `.gitignore` 排除：`*.env`、`ssh/`、`workdir/keys/`、`configs/secrets.json`、`deploy/pkg3/`、`halo-lab/tools|jars|work`、插件 jar、`workdir/db|indices|attachments|archive`、`.cache/.slidep`、`__pycache__/`、`halo-cn/output/`、`deploy/{loc,rem}.html`。
