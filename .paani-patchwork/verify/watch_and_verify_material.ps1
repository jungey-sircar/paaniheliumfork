# Waits for the running Paani build to finish, then verifies the chrome material.
#
# The link of paani.dll takes most of an hour and needs nearly all the machine's
# RAM, so nothing else may run against the build tree while it is going. This
# waits for siso to exit, records the build verdict, and only then launches
# Paani from the build tree for the pixel checks.
param(
    [int]$BuildPid = 19244,
    [string]$BuildLog = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\logs\paani_material.log',
    [int]$TimeoutMinutes = 300
)
$ErrorActionPreference = 'Continue'
$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$out = Join-Path $verify 'logs\material_verify.txt'
"WATCH START $(Get-Date -Format o) waiting for PID $BuildPid" | Out-File -Encoding utf8 $out

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while (Get-Process -Id $BuildPid -ErrorAction SilentlyContinue) {
    if ((Get-Date) -gt $deadline) {
        "WATCH ABORT: build still running after $TimeoutMinutes minutes" |
            Out-File -Append -Encoding utf8 $out
        exit 1
    }
    Start-Sleep -Seconds 30
}
"WAITED UNTIL $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $out

$tail = Get-Content $BuildLog -Tail 40 -ErrorAction SilentlyContinue
"BUILD LOG TAIL:`n$($tail -join "`n")" | Out-File -Append -Encoding utf8 $out

$exe = Join-Path 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default' 'paani.exe'
$exeInfo = Get-Item $exe -ErrorAction SilentlyContinue
if ($exeInfo) {
    "paani.exe $($exeInfo.Length) bytes, mtime $($exeInfo.LastWriteTime.ToString('o'))" |
        Out-File -Append -Encoding utf8 $out
} else {
    "paani.exe MISSING" | Out-File -Append -Encoding utf8 $out
}

Start-Process -FilePath powershell.exe -ArgumentList '-NoProfile', '-ExecutionPolicy',
'Bypass', '-File', (Join-Path $verify 'verify_material.ps1') -WindowStyle Hidden -Wait
'Verification driver finished.' | Out-File -Append -Encoding utf8 $out

python (Join-Path $verify 'score_material.py') *>> $out
"DONE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $out
