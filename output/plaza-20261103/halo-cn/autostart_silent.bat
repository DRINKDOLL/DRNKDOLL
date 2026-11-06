@echo off
chcp 65001 >nul
rem ============================================================
rem  警院成果展示广场 - 开机自启动脚本（修复版，绝对路径）
rem  本文件是项目内备份；真正生效的是 Startup 文件夹里的同名脚本
rem ============================================================

set "JAVA=C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\tools\jdk-21.0.13.0.2+1\bin\java.exe"
set "JAR=C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\jars\halo-2.27.2.jar"
set "WORKDIR=C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-cn"

netstat -ano | findstr ":8092" | findstr "LISTENING" >nul
if %errorlevel%==0 exit /b 0

cd /d "%WORKDIR%"

set "HTTP_PROXY="
set "HTTPS_PROXY="
set "NO_PROXY=127.0.0.1,localhost,::1"
set "no_proxy=127.0.0.1,localhost,::1"

start "" "%JAVA%" -Xms256m -Xmx512m -Dfile.encoding=UTF-8 -Dsun.jnu.encoding=UTF-8 -Duser.language=zh -Duser.country=CN -Duser.timezone=Asia/Shanghai -jar "%JAR%" --spring.config.additional-location=file:./config/ --server.port=8092 --server.address=0.0.0.0

exit /b 0
