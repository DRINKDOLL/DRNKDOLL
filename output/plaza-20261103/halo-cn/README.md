# Halo 2.27.2 中文化演示实例

面向「成果展示广场」基座选型的验证环境：**同一版本、同一参数、同一数据目录，可重复启动**，并把面向用户的界面文字统一为简体中文。

- 站点首页：http://127.0.0.1:8092/
- 管理后台：http://127.0.0.1:8092/console
- 验收报告页：http://127.0.0.1:8100/report.html
- 账号：`admin` / `Passw0rd!2026`（仅本地演示）

---

## 一、依赖清单

本机没有 Docker、没有系统级 JDK、WSL 被安全策略禁用，因此采用「便携运行时 + 官方 fat jar + 内嵌 H2」的纯进程方案，不依赖容器与外部数据库。

| 组件 | 版本 | 作用 | 校验 |
|---|---|---|---|
| 操作系统 | Windows 10/11 x64 | 运行环境 | — |
| JDK | Microsoft OpenJDK **21.0.13.0.2+1 LTS**（解压即用） | 运行 Halo | `java -version` |
| Halo | **2.27.2**（`halo-2.27.2.jar`，129 MB） | 应用本体 | SHA-256 `aa86f2e99b0430bd7a83daae24ad33760f7162154c147b6ff387e98787348d14` |
| 数据库 | 内嵌 H2（文件模式，随 jar 自带） | 持久化 | 无需安装 |
| 反向代理 | 无 | 直连 8092 | — |

> 版本选择依据：2.27.2 已覆盖此前复现的三类问题（UC 附件 SSRF ≤2.24.0、备份路径穿越 ≤2.24.2、角色委派提权 ≤2.26.1），避免用一个已知有漏洞的版本做演示基座。

JDK 与 jar 已在本机 `output/plaza-20261103/halo-lab/` 下，脚本默认复用；可用环境变量替换：

```bash
export JAVA_BIN=/path/to/jdk-21/bin/java.exe
export HALO_JAR=/path/to/halo-2.27.2.jar
```

---

## 二、目录结构

```
halo-cn/
├── bootstrap.sh            # 一键：预检 → 启动 → 站点中文化 → 主题中文化 → 重启 → 验收
├── reset.sh                # 归档现有数据目录，回到全新安装状态（归档而非删除）
├── env.sh                  # 版本号、校验和、端口、账号、JVM 参数（集中管理）
├── config/application.yaml # 唯一的应用配置（端口、数据目录、语言、时区、日志）
├── scripts/
│   ├── provision.py        # 幂等：安装、站点标识、语言、管理员名、示例文章标题与正文
│   ├── patch_theme.py      # 幂等：替换主题模板中硬编码的英文页脚
│   └── verify.py           # 验收：接口断言 + 首页可见文本英文扫描
├── report.html             # 验证报告页（读取 run/verify.json 与 shots/ 渲染）
├── workdir/                # Halo 数据目录（DB、附件、主题、插件、日志）
├── archive/                # reset.sh 归档的旧数据目录
├── shots/                  # 验收截图（英文浏览器上下文实拍）
├── run/                    # 进程号、流程日志、验收结果 JSON
└── logs/                   # JVM 标准输出
```

---

## 三、启动步骤

```bash
cd output/plaza-20261103/halo-cn
./bootstrap.sh          # 跑完流程后驻留，守护 Halo 进程
```

脚本依次执行：

1. **预检**：JDK 必须为 21；jar 的 SHA-256 必须与官方发布一致；端口被其他实例占用则直接报错退出。
2. **启动**：`java -Xms256m -Xmx1200m -Duser.timezone=Asia/Shanghai … -jar halo-2.27.2.jar --spring.config.additional-location=file:./config/ --server.port=8092`。
3. **站点中文化**：调用 API 完成安装与文案设置（详见第四节）。
4. **主题中文化**：扫描 `workdir/themes/*/templates` 中的硬编码英文并替换（主题包在安装后才释放，所以放在安装之后）。
5. **重启并验收**：模板有改动才重启；随后断言语言、标题、页脚，并扫描首页可见英文。

实测从空目录到验收通过耗时约 27 秒（首次启动 `Started Application in 13.124 seconds`）。

只跑流程不驻留（进程由外部守护时用）：

```bash
./bootstrap.sh --no-wait
```

从零重来：

```bash
./reset.sh && ./bootstrap.sh
```

`reset.sh` 采用**归档**而非删除：把 `workdir/`、`logs/` 移到 `archive/` 下并加时间戳，可回滚、可对比两次运行结果。

### 三个必须知道的坑

| 现象 | 原因 | 处理 |
|---|---|---|
| 启动报 `Port 62406 was already in use` | 宿主环境预设了 `SERVER__PORT=62406`，Spring 松散绑定会让**环境变量覆盖配置文件** | 启动时 `env -u SERVER__PORT` 清除，并用 `--server.port` 命令行参数（优先级最高）显式固定 |
| 脚本探活失败、`curl 127.0.0.1` 返回 502 | 宿主设置了 `HTTP_PROXY`，发往 127.0.0.1 的请求被转发到代理 | `env.sh` 中导出 `NO_PROXY=127.0.0.1,localhost`，脚本内 curl 统一加 `--noproxy '*'` |
| 探活一直不通过、`/system/setup` 返回 404 | 该路由只在 `Accept: text/html` 时返回安装页，`Accept: application/json` 会落到静态资源兜底 | 探活统一带 `Accept: text/html`；判定“是否已安装”改用 `configmaps/system` 是否可读 |
| 安装接口返回 415/404 | `POST /system/setup` 的路由按 `application/x-www-form-urlencoded` 匹配，不接收 JSON | 用表单编码提交，字段为 `username/password/email/siteTitle/language/externalUrl` |

---

## 四、配置说明

`config/application.yaml`（唯一配置源）：

```yaml
server:
  port: 8092
halo:
  external-url: http://127.0.0.1:8092
  work-dir: ./workdir
  security:
    basic-auth:
      disabled: false      # 仅供本地脚本化调用 API，生产必须关闭
spring:
  web:
    locale: zh_CN
logging:
  file:
    name: ./run/halo.log
```

JVM 参数固定为：`-Xms256m -Xmx1200m -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 -Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai`。

---

## 五、中文化做了什么

Halo 自身的中文翻译是完整的（控制台随包提供 zh-CN，主题 `theme-earth` 的 `i18n/zh_CN.properties` 54 个键全部有中文），因此工作重点不是「翻译词条」，而是**把默认英文的配置层文案与模板硬编码英文收敛到中文，并锁定语言**。

| 层次 | 原文 | 中文 | 实现方式 |
|---|---|---|---|
| 系统语言 | 随浏览器语言变化 | `zh-CN` 锁定 | 安装时 `language=zh-CN` + `systemconfigs/basic.language` |
| 站点标题 | `Halo SSRF Lab` | `警院成果展示广场` | `systemconfigs/basic.title` |
| 站点副标题 | 空 | `警务技术实训成果的展示、体验与反馈` | `systemconfigs/basic.subtitle` |
| 管理员显示名 | `Administrator` | `管理员` | `users/admin.spec.displayName` |
| 示例文章标题 | `Hello Halo` | `你好，Halo` | 文章 `spec.title` |
| 示例文章正文 | 正文小标题 `Hello Halo` | `你好，Halo` | 快照正文经控制台接口改写后重新发布 |
| 页脚版权句 | `All Rights Reserved. Powered by` | `版权所有，保留所有权利。技术支持：` | 2.27.2 的主题模板已内置中文，脚本保留整句替换逻辑用于旧版或其他主题 |

### 术语对照（全站统一）

| 英文 | 统一译法 | 说明 |
|---|---|---|
| Post / Posts | 文章 | 控制台「文章」，不译作「帖子」 |
| Page / Pages | 页面 | 单页，与文章区分 |
| Category | 分类 | |
| Tag | 标签 | |
| Attachment | 附件 | |
| Theme | 主题 | 外观层 |
| Plugin | 插件 | |
| Comment / Reply | 评论 / 回复 | 回复是评论的下级 |
| Dashboard | 仪表盘 | |
| Console | 控制台 | 后台入口 |
| User | 用户 | |
| Role | 角色 | |
| Backup | 备份 | |
| Migration | 迁移 | |

**保留原文的部分**（属品牌与技术专名，不翻译）：`Halo`、`GitHub`、`Markdown`、`RSS`、`API`、`URL`、`QQ`、`WeChat`，以及语言切换器中的 `English` / `Español` / `繁體中文`（按母语显示是刻意设计）。

### 中文化的边界

- **可改**：站点配置、内容、主题模板与主题语言包——这些在 `workdir/` 下，升级不覆盖数据目录。
- **不可外部改**：控制台前端打包在 jar 内（`console/` 静态资源），要改只能改源码重新打包。实测 2.27.2 的控制台在 `en-US` 浏览器下仍为中文，无需干预。
- **版本差异**：2.24.0 的主题 `footer.html` 第 68、154 行是硬编码英文（`All Rights Reserved. Powered by`）；2.27.2 已改为中文，因此本实例的模板替换步骤实际是空操作。脚本保留该逻辑，换主题或回退版本时仍可用。
- **升级风险**：主题模板补丁会在主题升级时被覆盖，升级后需重跑 `scripts/patch_theme.py`。

---

## 六、验收

```bash
python scripts/verify.py --base http://127.0.0.1:8092 --username admin --password 'Passw0rd!2026'
```

检查项与结果写入 `run/verify.json`：

| 检查项 | 判据 |
|---|---|
| 站点语言锁定 | `/api/v1alpha1/settings/system` → `basic.language == zh-CN` |
| 站点标题为中文字段 | 标题含中日韩统一表意文字 |
| 首页 `html lang` | 以 `zh` 开头 |
| 首页无英文残留 | 可见文本中的英文词（白名单除外）为空 |
| 页脚已中文化 | 含「版权所有」且不含 `All Rights Reserved` |
| 控制台 `html lang` | 以 `zh` 开头 |
| 管理员显示名中文化 | 显示名含中文 |

浏览器语言无关性另行验证：用 `en-US` + `Accept-Language: en-US` 的浏览器上下文访问，界面仍为中文（截图见 `shots/`）。

---

## 七、可复现性说明

- 版本、校验和、端口、JVM 参数、配置全部写死在 `env.sh` 与 `config/application.yaml`，无隐式默认值。
- 数据目录独立，`reset.sh` 可随时回到全新安装态。
- `provision.py`、`patch_theme.py` 均幂等：重复执行只会把状态收敛到目标值，不产生重复数据。
- 首次启动约 13 秒（`Started Application in 13.124 seconds`），脚本探活上限 180 秒。
