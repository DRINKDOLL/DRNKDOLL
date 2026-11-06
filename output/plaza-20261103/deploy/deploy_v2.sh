#!/bin/bash
# 服务器端一键部署（在 /opt/plaza 的完整包解压后执行）
# 用法：bash /root/deploy_v2.sh
set -euo pipefail

echo "===== 1/6 停服务 ====="
systemctl stop plaza || true
sleep 2

echo "===== 2/6 备份旧版本 ====="
TS=$(date +%Y%m%d%H%M%S)
mkdir -p /opt/plaza/backup
[ -f /opt/plaza/halo.jar ] && mv /opt/plaza/halo.jar /opt/plaza/backup/halo.jar.prev-$TS
cp -a /opt/plaza/workdir/db/halo-next.mv.db /opt/plaza/backup/halo-next.mv.db.before-v2
cp -a /opt/plaza/workdir/themes /opt/plaza/backup/themes-$TS
echo "备份完成：$TS"

echo "===== 3/6 解压新版（覆盖 jar / 模板 / 静态 / 附件 / gateway）====="
tar xzf /root/plaza-full.tar.gz -C /opt/plaza
grep -c buildRaw /opt/plaza/halo.jar >/dev/null 2>&1 || true
echo "jar 大小：$(du -h /opt/plaza/halo.jar | cut -f1)"

echo "===== 4/6 网关服务 ====="
cat > /etc/systemd/system/gateway.service <<'UNIT'
[Unit]
Description=Jingyuan Plaza - Unified Gateway Stub (IF-08 / reserved, localhost:8094)
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/plaza
EnvironmentFile=/opt/plaza/config/gateway.env
ExecStart=/usr/bin/python3.11 -m gateway.server
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

if [ ! -f /opt/plaza/config/gateway.env ]; then
  umask 077
  cat > /opt/plaza/config/gateway.env <<'ENV'
PLAZA_GW_HOST=127.0.0.1
PLAZA_GW_PORT=8094
ENV
  echo "PLAZA_GW_INTERNAL_SIGN_SECRET=$(openssl rand -hex 32)" >> /opt/plaza/config/gateway.env
  chmod 600 /opt/plaza/config/gateway.env
fi

systemctl daemon-reload
systemctl enable gateway >/dev/null 2>&1

echo "===== 5/6 启动 ====="
systemctl start plaza
for i in $(seq 1 40); do
  c=$(curl -s -o /dev/null -m 3 -w "%{http_code}" http://127.0.0.1:8092/ || true)
  [ "$c" = "200" ] && break
  sleep 3
done
echo "Halo: $c"
systemctl start gateway
sleep 2
systemctl reload nginx || systemctl restart nginx
sleep 1

echo "===== 6/6 验收 ====="
echo -n "首页        : "; curl -s -o /dev/null -m 10 -w "%{http_code}\n" http://127.0.0.1/
echo -n "详情页      : "; curl -s -o /dev/null -m 10 -w "%{http_code}\n" http://127.0.0.1/archives/work-traffic
echo -n "控制台      : "; curl -s -o /dev/null -m 10 -w "%{http_code}\n" http://127.0.0.1/console
echo -n "管理门禁(应401): "; curl -s -o /dev/null -m 8 -w "%{http_code}\n" http://127.0.0.1/api/manage/achievements
echo -n "网关接口(应401/403，缺签名): "; curl -s -o /dev/null -m 8 -w "%{http_code}\n" http://127.0.0.1/api/v1/internal/works
echo -n "控制台编辑器补丁(应>=1): "; curl -s -m 10 http://127.0.0.1/ui-assets/use-session-keep-alive-D8zQp1gm.js | grep -c buildRaw || true
echo "服务状态    : $(systemctl is-active plaza gateway nginx | tr '\n' ' ')"
START=$(grep -n "Started Application" /opt/plaza/logs/halo.log | tail -1 | cut -d: -f1)
echo "启动后 ERROR: $(tail -n +$START /opt/plaza/logs/halo.log | grep -c ERROR || true)"
