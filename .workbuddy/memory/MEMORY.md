# 项目长期约定

## 运行网页的固定指令

- 用户说「运行 / 启动 / 打开广场」等指令时，直接启动「警院成果展示广场」Halo 实例并打开首页预览。
- 启动方式：**优先用 PowerShell `Start-Process` 独立启动，且【不要带 `-RedirectStandardOutput/-RedirectStandardError`】**（java 进程由 Windows 独立托管，不会被后台任务层回收；Halo 自己用 logback 写日志到 `run/halo.log`，不依赖 stdout 重定向）。这是唯一稳定可靠的方式，已实测验证。
  - 曾踩过的两个坑（都导致「启动→过一会儿进程消失」）：
    1. `run_in_background` 后台任务启动的 java 进程，在任务被判 failed（退出码 1/127）后会被任务层连带回收，进程在 Spring 初始化极早期（「No active profile set」或「Finished repository scanning」）就消失。
    2. `Start-Process` 若带了 `-RedirectStandardOutput/-RedirectStandardError`，PowerShell 会话一结束重定向句柄断开，会让 java 在 R2DBC 初始化前静默退出。
  - Start-Process 正确命令（PowerShell）：
    1. 先 `Remove-Item Env:HTTP_PROXY/HTTPS_PROXY/http_proxy/https_proxy -ErrorAction SilentlyContinue`（否则复制环境时大小写键冲突报「已添加项 http_proxy/HTTP_PROXY」）。
    2. 命令（**不带任何重定向参数**）：
       ```
       $java = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\tools\jdk-21.0.13.0.2+1\bin\java.exe"
       $jar  = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\jars\halo-2.27.2.jar"
       $workdir = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-cn"
       $args = @("-Xms256m","-Xmx512m","-Dfile.encoding=UTF-8","-Dsun.jnu.encoding=UTF-8","-Duser.language=zh","-Duser.country=CN","-Duser.timezone=Asia/Shanghai","-jar",$jar,"--spring.config.additional-location=file:./config/","--server.port=8092","--server.address=0.0.0.0")
       Start-Process -FilePath $java -ArgumentList $args -WorkingDirectory $workdir -PassThru -WindowStyle Hidden
       ```
    3. 启动后 java 进程 PID 是启动器返回的 `$p.Id`；实际监听进程 PID 会不同（java.exe 会 fork），用 `tasklist | grep java` + `netstat -ano | grep :8092` 确认真实监听 PID。
    4. 日志看 `halo-cn/run/halo.log`（logback 写入，比 `logs/halo.out` 更可靠，因为没重定向时 stdout 不落盘）。
  - 注意：`config/application.yaml` 里已有端口/中文等配置，命令行 `--server.port/--server.address` 覆盖即可；不要依赖 `&` 后台（会随命令会话中断被连带杀掉）。
- 启动命令（在 `output/plaza-20261103/halo-cn/` 下），**java.exe 与 jar 一律用绝对路径**（相对路径 `../halo-lab/...` 在后台任务里偶发「命令未找到」退出码 127，导致进程没起来）：
  ```
  cd "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-cn" && \
  source ./env.sh && \
  env -u SERVER__PORT -u SERVER__HOST -u SERVER_PORT -u SERVER_ADDRESS \
    NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
    "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-lab/tools/jdk-21.0.13.0.2+1/bin/java.exe" \
    -Xms256m -Xmx512m \
    -jar "C:/Users/LENOVO/Desktop/成果广场/output/plaza-20261103/halo-lab/jars/halo-2.27.2.jar" \
    --spring.config.additional-location=file:./config/ \
    --server.port=8092 --server.address=0.0.0.0 > logs/halo.out 2>&1
  ```
- 服务信息：首页 http://127.0.0.1:8092/ ；管理后台 http://127.0.0.1:8092/console；局域网 http://10.1.1.239:8092/。
- 登录凭据（两个账号，每次「运行」都要一并列出）：
  - 管理员：用户名 admin / 密码 Passw0rd!2026（可访问 /console 管理后台）
  - 普通用户：用户名 student / 密码 Student!2026（角色 post-author「作者」，登录后跳转 /uc 个人中心，**不能访问管理后台**，适合日常登录）
  - 用户要求：每次「运行」启动/打开网页后，务必把两个账号以「用户名：xxx / 密码：xxx」清晰易读的格式一并发出，并注明哪个是管理员、哪个是普通用户。
- 启动后轮询首页直到 HTTP 200，再用 present_files 打开 http://127.0.0.1:8092/ 预览。
- 端口被占先确认旧进程；H2 文件被锁时报 MVStoreException 时，先确保 8092 端口真正释放再启动。
- 后台任务的退出码通知（127 / 1073807364 等）不一定是真失败：Java 进程可能已独立存活继续初始化。收到失败通知后，务必先 `curl` 实测首页 HTTP 状态 + `tasklist` 查 java 进程，再决定是否重启，不要仅凭退出码误判。
- 若实测首页 000 且无 java 进程，说明实例确实没起来，需重新用后台任务启动。

## 定制 Halo 界面的两条通道（已验证）

- **主题模板**：`workdir/themes/theme-earth/templates/**`，改完必须**重启实例**（Thymeleaf 生产模式缓存模板）。
- **核心静态资源（如登录页）**：`workdir/static/**` 会**覆盖 jar 内 `BOOT-INF/classes/static/**`**，改完**无需重启**即刻生效（`/images/`、`/styles/` 均适用）。
  - 已用此通道实现登录页改造：`static/images/wordmark.svg`（站名标题）、`static/images/login-background.jpeg`（地球背景）、`static/styles/main.css`（复制 jar 原版后追加覆盖样式）。
  - ⚠️ 静态资源带一年期 `max-age` 缓存，且 URL 固定为 `?v=2.27.2`，**用户浏览器一旦缓存旧副本，服务端怎么改都看不到**（需 `Ctrl+Shift+R`）。因此「改登录页视觉」优先走下面的模板通道，不要依赖静态资源替换。
- **核心 Thymeleaf 模板（登录/注册/找回密码/错误页）**：`workdir/templates/` 默认不生效，**必须**在 `config/application.yaml` 里配置 `spring.thymeleaf.prefix: file:./workdir/templates/`（可加 `cache: false`），才能覆盖 jar 内 `BOOT-INF/classes/templates/`。
  - 模板来源：`jar xf halo-2.27.2.jar BOOT-INF/classes/templates` 全量提取（约 106 个文件，含 `*.properties` 语言包，缺了会丢中文文案）。
  - 登录页站名在 `gateway_fragments/common.html` 的 `haloLogo` fragment；背景在 `gateway_fragments/layout.html` 的 `<body class="gateway-page">`。改成内联样式最稳——HTML 响应是 `no-cache`，不受静态资源缓存影响。
  - 若曾内联覆盖过 `<style>`（如 `.halo-logo img{width:6em}`），同名选择器特异性相同时位置靠后的胜出，需抬高特异性（`body .xxx`）或用 `!important`。
  - `bootstrap.sh` 会校验 jar 的 sha256（`start.sh` 不校验）。只要不重跑 bootstrap，改 jar 是可用的最后手段（改前必须 `cp` 备份）。
- theme-earth 是预编译主题，Tailwind 按需生成的类（`text-4xl`/`text-6xl`/`font-bold`/`md:grid-cols-3`/`underline`/`decoration-*`/`underline-offset-2`/`transition-colors` 等）**不在 CSS 里**，改类名不生效；需要用内联 `style`（如 `clamp()`、`text-decoration`）或改用已编译的类（如 `lg:grid-cols-3`、`cursor-pointer`、`hover:text-gray-600`）。

## 文章正文为空 = 快照缺渲染产物（不是主题问题）

- 现象：详情页只有标题、正文区空白，但侧边目录/摘要正常。查 `GET /apis/api.console.halo.run/v1alpha1/posts/{name}/head-content`，若 `raw` 有内容而 `content` 为 0 字节，即此症。
- 原因：Halo 控制台保存文章时由**前端**把 markdown 编译成 HTML 再提交；用接口只写 raw 不会自动渲染。
- 修复（Basic auth admin/Passw0rd!2026 即可）：`PUT /apis/api.console.halo.run/v1alpha1/posts/{name}/content`，body `{raw, content, rawType:"markdown"}`，再 `PUT .../{name}/publish`（**必须 PUT，POST 404**）。
- 现成脚本：`halo-cn/scripts/render_post_content.py`（含简易 markdown→HTML；`--dry-run` / `--post NAME` / `--force` 从 baseSnapshot 恢复原稿）。
- 该 PostEndpoint 是 RouterFunction，可用路由仅：`posts`、`posts/{name}`、`posts/{name}/content`、`/release-content`、`/head-content`、`/snapshot`、`/revert-content`、`/publish`、`/unpublish`、`/recycle`；`/draft`、`posts/{name}`(GET) 都是 404。

## 成果详情爬虫（crawl_achievements.py）

- 位置：`halo-cn/scripts/crawl_achievements.py` + 配置 `scripts/achievement_sources.json`（slug → 来源 url / content_selector / summary / max_chars / max_images）。
- 纯标准库实现（urllib + html.parser 迷你 DOM），无 pip 依赖；`--dry-run` 只打印、`--slug X` 单项目、`--no-images`、`--prune-images`。
- 抓取流程：选取正文容器（selector 支持 `tag.cls` / `#id` / `.cls`，留空或正文过少时用 `auto_content` 兜底：一次 DFS 取「文本量≥最大值90% 且层级最深」的容器）→ 白名单抽块（h2-h4/p/ul/ol/table/figure/img/blockquote）→ `SECTION_SKIP` 丢弃安装/依赖/FAQ/许可类章节 → `polish()` 清洗 → 图片下载改写 → 写库发布。
- 可访问性事实：维基/百度百科抓不到；**阿里云开发者社区正文前端渲染，抓不到**；腾讯云开发者社区服务端渲染，最稳。
- 坑：`SKIP_CLASS_HINTS` 必须用精确 token（曾用 `mark` 误杀 `rno-markdown` 整篇正文）；`pre` 代码块会被主题 blur，直接跳过；图片 URL 需 `quote()` 处理空格括号。
- 图片落地：`workdir/static/images/achievements/<slug>/`，站内路径 `/images/achievements/...`，无需重启。
- 正文结构固定为：作品说明 / 技术方案与实现（中文导语 + 抓取摘录 + 图）/ 项目信息 / 体验方式 / 参考资料。
- 暗色：主题 `markdown-body` 没有暗色配色，必须在 main CSS 追加 `.dark #content ...` 覆盖，否则正文在暗色下不可读。

## 卡片渲染有两条路径（改卡片必须两边都改）

- 服务端：`modules/post-card.html`（+ `modules/featured-post-card.html` 置顶卡），被 index/category/author/tag/categories/tags 复用，改一处即全站生效。**注意 `archives.html`（文章页）有自己的列表结构，不复用 post-card，需要单独改。**
- 客户端：`index.html` 与 `category.html` **各有一份 `renderCard`**（分类切换时替换 `#post-list`）。只改模板不改 JS，一切换分类新增元素就消失；只改 JS 不改模板，首屏就看不到。
- 卡片简介已做成详情页链接（`<a>` 包住 `th:text` 的简介）；标题下方另有胶囊入口「查看项目详情 ›」（class `post-detail-link`），hover 样式追加在 `templates/assets/main-BaWd_1hx.css` 末尾（需 `!important` 才能覆盖内联样式）。

## 详情页「返回」入口的路由约定

- `post.html` 顶部与底部各一个 `a[data-post-back]`（文案节点 `[data-post-back-label]`），`</body>` 前内联脚本统一处理：同源 referrer → 目标为 referrer 地址、文案「返回上一页」，点击先 `history.back()`（还原来源页状态），400ms 未离开再 `location.assign` 兜底；无 referrer（新标签/外链）→ 回 `/`、文案「返回首页」。
- 首页分类筛选是客户端状态，已把状态写进 `#cat=<分类名>` hash（`categoryFilter.init()` 读、筛选后 `history.replaceState` 写），否则返回时筛选会丢。
- 公开成果详情接口（免鉴权）：`GET /apis/api.content.halo.run/v1alpha1/posts/{name}`，返回 Post 及 `content:{raw, content}`（content 即渲染后 HTML）；列表 `.../posts`、分类 `.../categories/{name}/posts`。

## 控制台 / 个人中心（Vue SPA）的定制方式

- 资源映射（`WebFluxConfig` 里硬编码，**workdir 无法覆盖**）：
  - `/console` → jar 内 `BOOT-INF/classes/ui/console.html`（响应头 `no-store`，改完普通刷新即生效）
  - `/uc` → jar 内 `BOOT-INF/classes/ui/uc.html`
  - `/ui-assets/**` → `classpath:/ui/ui-assets/`（React/Vue 打包产物，带 `.gz` 同名副本）
  - 只有 `/**` 才走 `workdir/static/`，且优先级低于上面三条。
- 控制台左上角「Halo」标志是 **内联 SVG**（`.sidebar__logo`，viewBox `0 0 2144 877`），没有独立图片文件，只存在于 JS 里，因此**改不了静态资源，只能改 jar 内的 `console.html`**。
- 已验证的改法（纯 CSS，零 JS，功能不受影响）：在 `console.html` 唯一那个 `<style>` 块里追加
  ```css
  .sidebar__logo{display:none!important}
  .sidebar__logo-container a::after{content:"警院成果展示广场";display:block;font-size:1.0625rem;font-weight:700;color:#0e1731;letter-spacing:.02em;white-space:nowrap;line-height:2rem}
  ```
  `line-height:2rem` 用来保持容器高度仍是 72px；原 `<a href="/" title="访问首页">` 不动，点击行为不变。侧边栏是固定白底 `#fff`、无暗色模式，故用深蓝文字。
- 更新 jar 的正确姿势：先 `Stop-Process` 停实例（Windows 下 jar 被占用无法写）→ `jar uf <jar> BOOT-INF/classes/ui/console.html BOOT-INF/classes/ui/console.html.gz`（**同时更新 `.gz`**，用 `gzip.compress(data, 9, mtime=0)` 生成）→ 启动。`jar uf` 是原地更新，条目总数与 manifest 不变，比重建 zip 安全。
- 备份文件：`halo-lab/jars/halo-2.27.2.jar.bak-20261104`（回滚即 `cp` 回去）。
- 控制台 SPA 有持续轮询，Playwright 用 `waitUntil:'networkidle'` 会超时，改用 `domcontentloaded` + 固定等待。
