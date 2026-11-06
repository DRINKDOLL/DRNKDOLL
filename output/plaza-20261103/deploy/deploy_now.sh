#!/bin/bash
# 本地驱动的一键部署（走 dpl.py 的 SSH 通道，无需先在服务器上放包）
# 用法：cd deploy && export DPL_HOST=... DPL_USER=root DPL_PASS=... && bash deploy_now.sh
set -uo pipefail
cd "$(dirname "$0")" || exit 1

PKG=plaza-full.tar.gz
need() { [ -f "$1" ] || { echo "缺少文件: $1"; exit 1; }; }
need "$PKG"; need plaza.conf; need gateway.service

echo "########## 1/6 停服务并备份 ##########"
python dpl.py exec '
set -e
TS=$(date +%Y%m%d%H%M%S); echo "TS=$TS"
systemctl stop plaza || true
sleep 2
mkdir -p /opt/plaza/backup
[ -f /opt/plaza/halo.jar ] && mv /opt/plaza/halo.jar /opt/plaza/backup/halo.jar.prev-$TS
cp -a /opt/plaza/workdir/db/halo-next.mv.db /opt/plaza/backup/halo-next.mv.db.before-v3
cp -a /opt/plaza/workdir/themes /opt/plaza/backup/themes-$TS
echo "旧 jar sha: $(sha256sum /opt/plaza/backup/halo.jar.prev-$TS | cut -c1-16)"
echo "备份写入 $TS" > /tmp/plaza_ts
du -sh /opt/plaza/backup | tail -1
' || { echo "!! 停服/备份失败，中止"; exit 1; }

echo "########## 2/6 上传并解压新版（121MB）##########"
python dpl.py push "$PKG" 'tar xzf - -C /opt/plaza && echo EXTRACT_OK && sha256sum /opt/plaza/halo.jar | cut -c1-16 && du -sh /opt/plaza/gateway' \
  || { echo "!! 上传/解压失败，中止"; exit 1; }

echo "########## 3/6 安装 gateway 单元与 nginx 配置 ##########"
python dpl.py push gateway.service 'cat > /etc/systemd/system/gateway.service' || exit 1
python dpl.py push plaza.conf 'cat > /etc/nginx/conf.d/plaza.conf' || exit 1

echo "########## 4/6 生成 gateway 环境变量并注册 ##########"
python dpl.py exec '
set -e
if [ ! -f /opt/plaza/config/gateway.env ]; then
  umask 077
  printf "PLAZA_GW_HOST=127.0.0.1\nPLAZA_GW_PORT=8094\n" > /opt/plaza/config/gateway.env
  echo "PLAZA_GW_INTERNAL_SIGN_SECRET=$(openssl rand -hex 32)" >> /opt/plaza/config/gateway.env
  chmod 600 /opt/plaza/config/gateway.env
  echo "gateway.env 已生成"
else
  echo "gateway.env 已存在，保留"
fi
ls -l /opt/plaza/config/gateway.env
chown -R root:root /opt/plaza/gateway
systemctl daemon-reload
systemctl enable gateway >/dev/null 2>&1 && echo "gateway enabled"
nginx -t 2>&1 | tail -2
' || exit 1

echo "########## 5/6 启动服务 ##########"
python dpl.py exec '
systemctl start plaza
for i in $(seq 1 40); do
  c=$(curl -s -o /dev/null -m 3 -w "%{http_code}" http://127.0.0.1:8092/ || true)
  [ "$c" = "200" ] && break
  sleep 3
done
echo "Halo 就绪: $c"
systemctl restart gateway; sleep 2
systemctl reload nginx || systemctl restart nginx
sleep 1
echo "服务状态: $(systemctl is-active plaza gateway nginx | tr "\n" " ")"
' || exit 1

echo "########## 6/6 验收 ##########"
python dpl.py exec '
p(){ printf "%-32s " "$1"; curl -s -o /dev/null -m 10 -w "%{http_code}\n" "http://127.0.0.1$2"; }
p "首页"                    "/"
p "详情页"                  "/archives/work-traffic"
p "docs（新）"              "/docs"
p "links（新）"             "/links"
p "moments（新）"           "/moments"
p "photos（新）"            "/photos"
p "favicon（新）"           "/favicon.ico"
p "后台登录页"              "/console"
p "管理门禁(应401)"         "/api/manage/achievements"
p "网关IF-08(应401/403)"    "/api/v1/internal/works"
printf "%-32s " "控制台编辑器补丁 buildRaw"; curl -s -m 10 http://127.0.0.1/ui-assets/use-session-keep-alive-D8zQp1gm.js | grep -c buildRaw
printf "%-32s " "端口(仅回环)"; ss -lntp | grep -E ":8092|:8093|:8094" | awk "{print \$4}" | tr "\n" " "; echo
START=$(grep -n "Started Application" /opt/plaza/logs/halo.log | tail -1 | cut -d: -f1)
echo "启动后 ERROR 数: $(tail -n +$START /opt/plaza/logs/halo.log | grep -c ERROR)"
journalctl -u gateway -n 4 --no-pager | tail -4
'
