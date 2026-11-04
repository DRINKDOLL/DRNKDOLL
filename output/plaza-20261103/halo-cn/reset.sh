#!/usr/bin/env bash
# 回到“全新安装”状态：把现有数据目录归档，而不是直接删除（可回滚、可对比）
set -euo pipefail
cd "$(dirname "$0")"
source ./env.sh

if [ -f run/halo.pid ]; then
  kill "$(cat run/halo.pid)" 2>/dev/null || true
  for _ in $(seq 1 20); do kill -0 "$(cat run/halo.pid)" 2>/dev/null || break; sleep 1; done
  rm -f run/halo.pid
fi

TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p archive
if [ -d workdir ]; then
  mv workdir "archive/workdir-${TS}"
  echo "已归档旧数据目录 → archive/workdir-${TS}"
fi
if [ -d logs ]; then
  mv logs "archive/logs-${TS}"
fi
mkdir -p workdir logs
rm -f run/patch.log run/verify.json
echo "已重置：workdir/、logs/ 为空。执行 ./bootstrap.sh 可重新从零复现。"
