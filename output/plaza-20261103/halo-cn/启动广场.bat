@echo off
chcp 65001 >nul
title 启动警院成果展示广场 (Halo)

rem 切换到脚本所在目录
cd /d "%~dp0"

set "JAR=..\halo-lab\jars\halo-2.27.2.jar"
set "JAVA=..\halo-lab\tools\jdk-21.0.13.0.2+1\bin\java.exe"

rem 检查是否已在运行（端口 8092 被占用则提示）
netstat -ano | findstr ":8092" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo [提示] 实例似乎已在运行。
    echo   本机访问: http://127.0.0.1:8092/
    echo   局域网:   http://10.1.1.239:8092/
    echo.
    pause
    exit /b 0
)

echo 正在启动 Halo 实例（端口 8092）...
echo 启动后请稍等约 10 秒，再打开浏览器访问。
echo.

start "" "%JAVA%" -Xms256m -Xmx512m -jar "%JAR%" --spring.config.additional-location=file:./config/ --server.port=8092 --server.address=0.0.0.0

echo 已发起启动。约 10 秒后可访问：
echo   本机访问: http://127.0.0.1:8092/
echo   局域网:   http://10.1.1.239:8092/
echo   管理后台: http://127.0.0.1:8092/console  (admin / Passw0rd!2026)
echo.
echo 关闭本窗口不会停止服务；如需停止，请关闭 java 进程。
echo.
pause
