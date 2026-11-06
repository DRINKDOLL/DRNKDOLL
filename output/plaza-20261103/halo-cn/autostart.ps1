# ============================================================
#  Plaza auto-start script (called by Windows Scheduled Task)
#  Managed by Task Scheduler, runs independent of any session
# ============================================================

$java = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\tools\jdk-21.0.13.0.2+1\bin\java.exe"
$jar  = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-lab\jars\halo-2.27.2.jar"
$workdir = "C:\Users\LENOVO\Desktop\成果广场\output\plaza-20261103\halo-cn"

# If 8092 is already listening, the instance is already running; exit.
$listening = Get-NetTCPConnection -LocalPort 8092 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Port 8092 already listening, skipping."
    exit 0
}

# Clear proxy vars so 127.0.0.1 is not forwarded.
Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:http_proxy -ErrorAction SilentlyContinue
Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:https_proxy -ErrorAction SilentlyContinue
$env:NO_PROXY = "127.0.0.1,localhost,::1"
$env:no_proxy = "127.0.0.1,localhost,::1"

$jvmArgs = @(
    "-Xms256m",
    "-Xmx512m",
    "-Dfile.encoding=UTF-8",
    "-Dsun.jnu.encoding=UTF-8",
    "-Duser.language=zh",
    "-Duser.country=CN",
    "-Duser.timezone=Asia/Shanghai",
    "-jar", $jar,
    "--spring.config.additional-location=file:./config/",
    "--server.port=8092",
    "--server.address=0.0.0.0"
)

Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting Halo ..."

# IMPORTANT: do NOT redirect stdout/stderr, otherwise java dies before R2DBC init.
# Let Halo write its own log via logback to run/halo.log.
$p = Start-Process -FilePath $java -ArgumentList $jvmArgs -WorkingDirectory $workdir `
    -PassThru -WindowStyle Hidden

Write-Output "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Started java process PID=$($p.Id)"