#!/usr/bin/env bash
# 固定参数集中在此，便于审计与复现
# 所有路径均相对于本文件所在目录

HALO_VERSION="2.27.2"
HALO_JAR_SHA256="aa86f2e99b0430bd7a83daae24ad33760f7162154c147b6ff387e98787348d14"

# 运行时与 jar 复用 halo-lab 已校验的副产物，可用环境变量覆盖
HALO_JAR="${HALO_JAR:-../halo-lab/jars/halo-${HALO_VERSION}.jar}"
JAVA_BIN="${JAVA_BIN:-../halo-lab/tools/jdk-21.0.13.0.2+1/bin/java.exe}"

PORT="8092"
BASE_URL="http://127.0.0.1:${PORT}"

ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Passw0rd!2026}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
SITE_TITLE="${SITE_TITLE:-警院成果展示广场}"
SITE_SUBTITLE="${SITE_SUBTITLE:-警务技术实训成果的展示、体验与反馈}"

# 中文地区参数：时区、编码、语言
JVM_OPTS="-Xms256m -Xmx1200m -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 -Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai"

# 宿主环境配置了 HTTP_PROXY，会让发往 127.0.0.1 的请求被转发而失败，这里强制直连
export NO_PROXY="127.0.0.1,localhost,::1"
export no_proxy="127.0.0.1,localhost,::1"
export NO_PROXY="$NO_PROXY"

