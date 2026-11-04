#!/usr/bin/env bash
# 一键复现：受影响版本 2.24.0 触发 → 修复版本 2.24.1 阻断
set -u
cd "$(dirname "$0")"
JAVA="./tools/jdk-21.0.13.0.2+1/bin/java.exe"
COMMON="--halo.security.basic-auth.disabled=false"

start() {  # $1=jar $2=port $3=workdir $4=log
  mkdir -p "$3"
  "$JAVA" -Xms256m -Xmx1200m -Dfile.encoding=UTF-8 -jar "$1" \
    --server.port="$2" --halo.work-dir="$3" --halo.external-url="http://127.0.0.1:$2" \
    $COMMON > "$4" 2>&1 &
  echo $!
}

waitup() {
  for _ in $(seq 1 60); do
    c=$(curl -s -o /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:$1/system/setup")
    [ "$c" != "502" ] && [ "$c" != "000" ] && return 0
    sleep 2
  done
  return 1
}

python listener.py 9999 > logs/listener.log 2>&1 &
LPID=$!
sleep 2

PID0=$(start jars/halo-2.24.0.jar 8090 ./work/v240 logs/halo-2.24.0.log)
waitup 8090 && echo "[+] 2.24.0 ready"
python repro.py --base http://127.0.0.1:8090 --target http://127.0.0.1:9999/probe --label vuln

PID1=$(start jars/halo-2.24.1.jar 8091 ./work/v241 logs/halo-2.24.1.log)
waitup 8091 && echo "[+] 2.24.1 ready"
rm -f evidence/callback.log
python repro.py --base http://127.0.0.1:8091 --target http://127.0.0.1:9999/probe --label fixed

kill "$PID0" "$PID1" "$LPID" 2>/dev/null
echo "[done] 证据见 evidence/"
