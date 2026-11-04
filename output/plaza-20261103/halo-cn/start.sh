#!/usr/bin/env bash
# 一键启动「警院成果展示广场」Halo 实例（可对外访问版）
# 绑定 0.0.0.0，本机与局域网均可访问；端口 8092
set -u
cd "$(dirname "$0")"
source ./env.sh

JAR="../halo-lab/jars/halo-${HALO_VERSION}.jar"
JAVA="../halo-lab/tools/jdk-21.0.13.0.2+1/bin/java.exe"
PORT="8092"

if netstat -ano 2>/dev/null | grep -q ":${PORT} .*LISTENING"; then
  echo "实例已在运行：http://127.0.0.1:${PORT}/"
  exit 0
fi

echo "启动 Halo ${HALO_VERSION}（绑定 0.0.0.0:${PORT}）..."
env -u SERVER__PORT -u SERVER__HOST -u SERVER_PORT -u SERVER_ADDRESS \
  NO_PROXY=127.0.0.1,localhost no_proxy=127.0.0.1,localhost \
  "$JAVA" -Xms256m -Xmx512m -jar "$JAR" \
    --spring.config.additional-location=file:./config/ \
    --server.port="${PORT}" \
    --server.address=0.0.0.0 \
    > logs/halo.out 2>&1 &

for i in $(seq 1 40); do
  code=$(curl -s -m 3 -o /dev/null -w "%{http_code}" --noproxy '*' "http://127.0.0.1:${PORT}/system/setup" 2>/dev/null)
  [ "$code" = "200" ] || [ "$code" = "302" ] && break
  sleep 3
done

# 局域网 IP：若为空，用 PowerShell 工具查得后填入（本机当前为 10.1.1.239）
LAN_IP="${LAN_IP:-10.1.1.239}"

echo ""
echo "启动完成"
echo "  本机访问   : http://127.0.0.1:${PORT}/"
echo "  局域网访问 : http://${LAN_IP}:${PORT}/"
echo "  管理后台   : http://127.0.0.1:${PORT}/console  (admin / ${ADMIN_PASSWORD})"
echo "  日志       : logs/halo.out"
