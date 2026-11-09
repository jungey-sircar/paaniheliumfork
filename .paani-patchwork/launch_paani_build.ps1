# Starts a Paani incremental build in its own process.
#
# A build launched as a console child dies with STATUS_DLL_INIT_FAILED_LOGOFF
# when that console is reaped, so it has to own its process (same reason
# launch_baseline.ps1 exists).  Everything after the log name is passed to
# run_build.py verbatim.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File launch_paani_build.ps1 `
#     paani_full.log -j 8 -k 0 chrome chromedriver setup mini_installer
param(
    [Parameter(Mandatory = $true, Position = 0)][string]$Log,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$BuildArgs
)
$ErrorActionPreference = 'Stop'

$root = 'E:\eric\PaaniBrowserChromiumFork'
$logDir = Join-Path $root '.paani-patchwork\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$stdOut = Join-Path $logDir $Log
$stdErr = Join-Path $logDir ($Log -replace '\.log$', '.err')
$runner = Join-Path $root 'paani-windows\build\patchwork\run_build.py'

$proc = Start-Process `
    -FilePath 'C:\Python313\python.exe' `
    -ArgumentList (@($runner) + $BuildArgs) `
    -WorkingDirectory (Join-Path $root 'paani-windows') `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdOut `
    -RedirectStandardError $stdErr `
    -PassThru

Write-Output ('STARTED PID=' + $proc.Id + ' LOG=' + $stdOut)
