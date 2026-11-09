# Starts the baseline build in its own process so that it is not attached to the
# console of the shell that launches it.  A `nohup` child dies with
# STATUS_DLL_INIT_FAILED_LOGOFF ("the window station is shutting down") as soon
# as that console goes away, which kills every action and compile in flight.
$ErrorActionPreference = 'Stop'

$root = 'E:\eric\PaaniBrowserChromiumFork'
$logDir = Join-Path $root '.paani-patchwork\logs'
$log = Join-Path $logDir $args[0]
$threads = if ($args.Count -gt 1) { $args[1] } else { '6' }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$proc = Start-Process `
    -FilePath 'C:\Python313\python.exe' `
    -ArgumentList @('paani-windows/build.py', '--baseline', '--profile', 'personal', '-j', $threads) `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $log `
    -RedirectStandardError (Join-Path $logDir ($args[0] -replace '\.log$', '.err')) `
    -PassThru

Write-Output ("STARTED PID=" + $proc.Id + " J=" + $threads + " LOG=" + $log)
