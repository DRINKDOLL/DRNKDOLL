#!/bin/bash
echo "=== 服务状态 ==="
systemctl is-active plaza nginx
echo "--- 开机自启 ---"
systemctl is-enabled plaza nginx
echo "=== 连续运行时长 ==="
uptime -p
echo "=== 监听端口 ==="
ss -lntp | grep -E ':80 |:8092 ' | awk '{print $4, $6}'
echo "=== 部署目录 ==="
ls -lh /opt/plaza/ | head -8
echo "=== JDK 版本 ==="
/opt/jdk21/bin/java -version 2>&1 | head -1
echo "=== 资源占用 ==="
free -m | awk 'NR==2{printf "内存 %s MB / %s MB\n", $3, $2}'
df -h / | awk 'NR==2{printf "磁盘 %s / %s (%s)\n", $3, $2, $5}'
echo "=== 插件状态 ==="
curl -s -m 15 -u "admin:Passw0rd!2026" "http://127.0.0.1:8092/apis/api.console.halo.run/v1alpha1/plugins" \
 | python3 -c "
import sys, json
d = json.load(sys.stdin)
items = d.get('items', [])
ok = sum(1 for p in items if (p.get('status') or {}).get('phase') == 'STARTED')
print('插件总数 %d, STARTED %d' % (len(items), ok))
"
echo "=== 最近一次启动后的 ERROR 数 ==="
START=$(grep -n "Started Application" /opt/plaza/logs/halo.log | tail -1 | cut -d: -f1)
tail -n +"$START" /opt/plaza/logs/halo.log | grep -c ERROR
echo "=== 备份 ==="
ls -1 /opt/plaza/backup/ 2>/dev/null | tail -3
