#!/usr/bin/env bash
# ============================================================
# Halo 2.27.2 中文化演示实例 · 一键可复现启动脚本
#
#   1. 预检：Java 版本 / jar 校验和 / 端口占用
#   2. 启动：固定 JVM 参数 + 固定配置目录 + 独立数据目录
#   3. 主题中文化：替换主题模板中硬编码的英文页脚（改后自动重启）
#   4. 站点中文化：初始化安装 + 站点标识 / 语言 / 示例内容
#   5. 验收：断言语言与标题，扫描首页可见文本的英文残留
#
#   用法：
#     ./bootstrap.sh              跑完流程后驻留，守护 Halo 进程（Ctrl-C 结束）
#     ./bootstrap.sh --no-wait    只跑流程不驻留（进程由外部守护时使用）
#   幂等：已安装跳过安装，已中文化跳过替换，重复执行结果一致。
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"
source ./env.sh

KEEP_ALIVE=1
[ "${1:-}" = "--no-wait" ] && KEEP_ALIVE=0

PID_FILE="run/halo.pid"
mkdir -p run logs workdir

log()  { printf '\n\033[36m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
die()  { printf '\n\033[31m[失败]\033[0m %s\n' "$*" >&2; exit 1; }
curl_local() { curl -s --noproxy '*' "$@"; }

# ---------- 1. 预检 ----------
log "1/5 环境预检"
[ -x "$JAVA_BIN" ] || die "未找到 Java 运行时：$JAVA_BIN（需 Microsoft OpenJDK 21）"
JAVA_VER="$("$JAVA_BIN" -version 2>&1 | head -1)"
echo "  Java  : $JAVA_VER"
case "$JAVA_VER" in *'"21.'*) : ;; *) die "需要 JDK 21，当前为 $JAVA_VER";; esac

[ -f "$HALO_JAR" ] || die "未找到 Halo jar：$HALO_JAR"
ACTUAL_SHA="$(sha256sum "$HALO_JAR" | cut -d' ' -f1)"
[ "$ACTUAL_SHA" = "$HALO_JAR_SHA256" ] || die "jar 校验和不匹配：$ACTUAL_SHA"
echo "  Halo  : ${HALO_VERSION}  sha256=${ACTUAL_SHA:0:16}…  ✔"

# 未安装返回 200（安装页），已安装返回 302（跳转登录页），两者都算就绪
is_up() { curl_local -o /dev/null -w '%{http_code}' --max-time 3 "${BASE_URL}/system/setup" 2>/dev/null | grep -qE '^(200|302)$'; }

start_halo() {
  echo "  启动 Halo ..."
  # 宿主环境可能预设 SERVER__PORT / SERVER__HOST（Spring 松散绑定会覆盖配置文件），
  # 这里清除这些变量，并用命令行参数显式固定端口与监听地址（优先级最高）。
  # shellcheck disable=SC2086
  env -u SERVER__PORT -u SERVER__HOST -u SERVER_PORT -u SERVER_ADDRESS \
    "$JAVA_BIN" $JVM_OPTS -jar "$HALO_JAR" \
      --spring.config.additional-location=file:./config/ \
      --server.port="${PORT}" \
      --server.address=127.0.0.1 \
      > logs/halo.out 2>&1 &
  HALO_PID=$!
  echo "$HALO_PID" > "$PID_FILE"
}

wait_ready() {
  local i
  for i in $(seq 1 90); do
    if is_up; then echo "  服务就绪（约 $((i * 2))s）"; return 0; fi
    sleep 2
  done
  tail -30 logs/halo.out >&2
  die "启动超时，请查看 logs/halo.out"
}

stop_halo() {
  [ -f "$PID_FILE" ] || return 0
  local pid; pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
  rm -f "$PID_FILE"
}

# ---------- 2. 启动 ----------
log "2/5 启动实例（端口 ${PORT}）"
if is_up; then
  echo "  实例已在运行，复用"
  HALO_PID="$(cat "$PID_FILE" 2>/dev/null || echo 0)"
else
  start_halo
  wait_ready
fi

# ---------- 3. 站点中文化 ----------
log "3/5 站点配置与内容中文化"
python scripts/provision.py \
  --base "$BASE_URL" \
  --username "$ADMIN_USERNAME" \
  --password "$ADMIN_PASSWORD" \
  --email "$ADMIN_EMAIL" \
  --title "$SITE_TITLE" \
  --subtitle "$SITE_SUBTITLE"

# ---------- 4. 主题模板中文化 ----------
# 主题包在安装完成后才由 Halo 释放到数据目录，因此放在安装之后
log "4/5 主题模板中文化"
for _ in $(seq 1 30); do [ -d workdir/themes ] && break; sleep 2; done
PATCHED=0
if python scripts/patch_theme.py --workdir ./workdir | tee run/patch.log | grep -q "已中文化"; then
  PATCHED=1
fi

# ---------- 5. 重启生效并验收 ----------
if [ "$PATCHED" = "1" ]; then
  log "5/5 重启以加载中文模板"
  stop_halo
  sleep 3
  start_halo
  wait_ready
else
  log "5/5 模板无改动，无需重启"
fi

echo ""
set +e
python scripts/verify.py --base "$BASE_URL" --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD"
VERIFY_RC=$?
set -e

log "完成"
echo "  站点首页 : ${BASE_URL}/"
echo "  管理后台 : ${BASE_URL}/console  （${ADMIN_USERNAME} / ${ADMIN_PASSWORD}）"
echo "  运行日志 : logs/halo.out"

if [ "$KEEP_ALIVE" = "1" ]; then
  echo ""
  echo "  脚本驻留中，Halo 进程由本脚本守护；按 Ctrl-C 结束。"
  wait "$HALO_PID" 2>/dev/null || true
fi
exit "$VERIFY_RC"
