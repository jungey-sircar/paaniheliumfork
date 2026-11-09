# Waits for an in-flight relink to finish, then runs the staged ad-blocker
# verification chain against a fresh headless Paani profile.
#
# This is a PowerShell driver rather than a bash one on purpose: a bash tree
# started from the agent's shell is killed when that shell's job is reaped,
# while Start-Process children of Python (the build) survive. The verdict is
# appended to auto_verify_result.txt either way.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File auto_verify.ps1 `
#     -BuildPid 2496 -Port 9341 -Profile profile10 `
#     -BuildLog ..\.paani-patchwork\logs\paani_hook_order.log
param(
    [Parameter(Mandatory = $true)][int]$BuildPid,
    [int]$Port = 9338,
    [string]$Profile = 'profile8',
    [string]$BuildLog = '',
    [switch]$SkipBuildWait
)
$ErrorActionPreference = 'Continue'

$root = 'E:\eric\PaaniBrowserChromiumFork'
$verify = Join-Path $root '.paani-patchwork\verify'
$out = Join-Path $root 'paani-windows\build\src\out\Default'
$logDir = Join-Path $verify 'logs'
$result = Join-Path $logDir 'auto_verify_result.txt'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Note($text) {
    $line = ('[' + (Get-Date -Format 'HH:mm:ss') + '] ' + $text)
    Add-Content -Path $result -Value $line
    Write-Output $line
}

Set-Content -Path $result -Value ('=== auto verify armed for build pid ' + $BuildPid + ' at ' + (Get-Date -Format 'HH:mm:ss') + ' ===')

if (-not $SkipBuildWait) {
    Note 'waiting for the build to exit'
    while ($null -ne (Get-Process -Id $BuildPid -ErrorAction SilentlyContinue)) {
        Start-Sleep -Seconds 20
    }
    Note 'build pid gone'
}

if ($BuildLog -and (Test-Path $BuildLog)) {
    Note '--- build verdict tail ---'
    Add-Content -Path $result -Value ((Get-Content -Path $BuildLog -Tail 15 -ErrorAction SilentlyContinue) -join "`n")
}

Note '--- artifacts ---'
foreach ($name in 'paani.exe', 'paani.dll', 'mini_installer.exe', 'setup.exe') {
    $p = Join-Path $out $name
    if (Test-Path $p) {
        $i = Get-Item $p
        Note ($name + '  ' + [math]::Round($i.Length / 1MB, 1) + ' MB  ' + $i.LastWriteTime.ToString('MM-dd HH:mm'))
    } else {
        Note ($name + '  MISSING')
    }
}

Note '--- freeing the binary lock ---'
Get-Process paani -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ($out + '*') } | ForEach-Object {
    Stop-Process -Id $_.Id -Force
    Note ('killed stale paani pid ' + $_.Id)
}
Start-Sleep -Seconds 3

Note ('--- launching headless paani, profile ' + $Profile + ' port ' + $Port + ' ---')
& (Join-Path $verify 'launch_diag.ps1') -Profile $Profile -Port $Port

$up = $false
for ($i = 1; $i -le 40; $i++) {
    try {
        Invoke-RestMethod -Uri ('http://127.0.0.1:' + $Port + '/json/version') -TimeoutSec 3 | Out-Null
        $up = $true
        Note ('CDP up after ' + $i + ' probes')
        break
    } catch { Start-Sleep -Seconds 3 }
}
if (-not $up) {
    Note 'FAILED: the browser never opened a DevTools port; nothing below this line ran'
    exit 1
}
Start-Sleep -Seconds 6

Note '--- engine startup lines ---'
$errLog = Join-Path $logDir ($Profile + '.err')
if (Test-Path $errLog) {
    $hits = Select-String -Path $errLog -Pattern 'Paani: ', 'No binder found' -SimpleMatch -ErrorAction SilentlyContinue
    if ($hits) { $hits | ForEach-Object { Note $_.Line } } else { Note '(no Paani lines in the stderr log)' }
} else {
    Note ('no stderr log at ' + $errLog)
}

function RunNode($script, $arguments, $label) {
    Note ('--- ' + $label + ' ---')
    $o = Join-Path $logDir ($Profile + '_node_out.txt')
    $e = Join-Path $logDir ($Profile + '_node_err.txt')
    $proc = Start-Process -FilePath 'node' `
        -ArgumentList ((@((Join-Path $verify $script)) + $arguments)) `
        -WorkingDirectory $verify -NoNewWindow -PassThru `
        -RedirectStandardOutput $o -RedirectStandardError $e
    $proc.WaitForExit()
    Note ('node exit ' + $proc.ExitCode)
    if (Test-Path $o) { Add-Content -Path $result -Value ((Get-Content $o) -join "`n") }
    if (Test-Path $e) { Add-Content -Path $result -Value (('stderr: ' + ((Get-Content $e) -join "`n"))) }
}

RunNode 'cdp_state_json.mjs' @("$Port") 'stage 0: page state as JSON'
RunNode 'cdp_outcomes.mjs' @("$Port", 'http://127.0.0.1:8731/trackertest.html', '25') 'stage 1: per-request outcomes on the tracker page'
RunNode 'verify_paani.mjs' @("$Port") 'stage 2: five stage counter / allowlist chain'
RunNode 'cdp_state_json.mjs' @("$Port") 'stage 3: page state after the chain'

Note '--- engine lines after the run ---'
if (Test-Path $errLog) {
    Select-String -Path $errLog -Pattern 'Paani: ', 'No binder found' -SimpleMatch -ErrorAction SilentlyContinue |
        ForEach-Object { Note $_.Line }
}
Note '=== done ==='
