@echo off
rem 开机自启：静默启动 Halo，不弹出窗口
cd /d "%~dp0"

set "JAR=..\halo-lab\jars\halo-2.27.2.jar"
set "JAVA=..\halo-lab\tools\jdk-21.0.13.0.2+1\bin\java.exe"

netstat -ano | findstr ":8092" | findstr "LISTENING" >nul
if %errorlevel%==0 exit /b 0

start "" /b "%JAVA%" -Xms256m -Xmx512m -jar "%JAR%" --spring.config.additional-location=file:./config/ --server.port=8092 --server.address=0.0.0.0
