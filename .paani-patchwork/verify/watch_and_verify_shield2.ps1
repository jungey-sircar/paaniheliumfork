# Waits for the relink, verifies the toolbar shield, and installs only if the
# verification passed.
#
# The build is judged by the exit code run_build.py prints, not by a pipeline
# exit code, so the log is the source of truth.  The installer runs only when
# the phase1/phase2 numbers show that Paani's own engine blocked the ad and
# that the allowlist released it again.
param(
    [int]$BuildPid = 16308,
    [string]$BuildLog = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\logs\paani_relink_0810.log',
    [string]$NinjaLog = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\logs\build.log',
    [string]$OutDir = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
)
$ErrorActionPreference = 'Continue'
$root = 'E:\eric\PaaniBrowserChromiumFork'
$logs = Join-Path $root '.paani-patchwork\logs'
$out = Join-Path $logs 'shield2_verify.log'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $out

function Say([string]$m) {
    $line = "$(Get-Date -Format HH:mm:ss) $m"
    Write-Host $line
    $line | Out-File -Append -Encoding utf8 $out
}

# --- wait for the build -------------------------------------------------
$last = ''
while ($true) {
    $p = Get-Process -Id $BuildPid -ErrorAction SilentlyContinue
    if ($null -eq $p) { break }
    if (Test-Path $NinjaLog) {
        $tail = (Get-Content $NinjaLog -Tail 1 -ErrorAction SilentlyContinue) -join ''
        if ($tail -and $tail -ne $last) {
            $last = $tail
            Say "build: $tail"
        }
    }
    Start-Sleep -Seconds 45
}
Say 'build process finished'

$log = ''
if (Test-Path $BuildLog) { $log = (Get-Content $BuildLog -Raw -ErrorAction SilentlyContinue) }
if (-not $log) { $log = Get-Content $NinjaLog -Raw -ErrorAction SilentlyContinue }
$code = -1
if ($log -match 'build exit code:\s*(\d+)') { $code = [int]$Matches[1] }
Say "build exit code: $code"

if ($code -ne 0) {
    Say 'BUILD FAILED -- not verifying, not installing'
    Get-Content $NinjaLog -Tail 60 -ErrorAction SilentlyContinue |
        Out-File -Append -Encoding utf8 $out
    Say 'STOPPED'
    exit 1
}
if (-not (Test-Path (Join-Path $OutDir 'paani.exe'))) {
    Say 'paani.exe missing -- stopping'
    exit 1
}
$exe = Get-Item (Join-Path $OutDir 'paani.exe')
Say ("paani.exe built {0} ({1} bytes)" -f $exe.LastWriteTime, $exe.Length)

# --- verify -------------------------------------------------------------
$vout = Join-Path $logs 'shield2_verify_stdout.log'
Say 'running verify_shield2.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File `
    (Join-Path $root '.paani-patchwork\verify\verify_shield2.ps1') *>&1 |
    Tee-Object -FilePath $vout | Out-Null
$vres = (Get-Content $vout -Raw -ErrorAction SilentlyContinue)
$vres | Out-File -Append -Encoding utf8 $out
Say 'verification output:'
Write-Host $vres

$blocked = -1
$allowed = -1
if ($vres -match 'phase1_blocked=(\d+)\s+phase2_allowed=(\d+)') {
    $blocked = [int]$Matches[1]
    $allowed = [int]$Matches[2]
}
Say "phase1_blocked=$blocked phase2_allowed=$allowed"

if ($blocked -le 0 -or $allowed -ne 0) {
    Say 'VERIFICATION DID NOT PASS -- not installing'
    Say 'STOPPED'
    exit 1
}

# --- install ------------------------------------------------------------
$inst = Join-Path $OutDir 'mini_installer.exe'
Say "running $inst"
$p = Start-Process -FilePath $inst -WorkingDirectory $OutDir -PassThru -Wait
Say "mini_installer exit code: $($p.ExitCode)"

$target = Join-Path $env:LOCALAPPDATA 'Paani'
if (Test-Path $target) {
    Get-ChildItem $target -Filter '*.exe' -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 10 FullName, Length, LastWriteTime |
        Out-File -Append -Encoding utf8 $out
    Say "installed at $target"
} else {
    Say "no install directory at $target"
}
Say 'DONE'
