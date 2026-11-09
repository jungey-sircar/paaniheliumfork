$ErrorActionPreference = 'SilentlyContinue'

Write-Output "--- processes matching link/lld/pdb ---"
foreach ($p in Get-Process | Where-Object { $_.ProcessName -match 'link|lld|pdb|clang' }) {
    Write-Output ($p.ProcessName + " PID=" + $p.Id +
        " CPUsec=" + [math]::Round($p.CPU, 1) +
        " WS_MB=" + [math]::Round($p.WorkingSet64 / 1MB, 0) +
        " Priv_MB=" + [math]::Round($p.PrivateMemorySize64 / 1MB, 0))
}

Write-Output "--- build.py / siso / autoninja ---"
foreach ($p in Get-Process | Where-Object { $_.ProcessName -match 'python|siso' }) {
    Write-Output ($p.ProcessName + " PID=" + $p.Id + " WS_MB=" + [math]::Round($p.WorkingSet64 / 1MB, 0))
}

Write-Output "--- chrome.dll.tmp growth (two samples, 20s apart) ---"
$tmp = Get-ChildItem 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\chrome.dll*' -ErrorAction SilentlyContinue
foreach ($f in $tmp) { Write-Output ($f.Name + " " + $f.Length + " " + $f.LastWriteTime) }
Start-Sleep -Seconds 20
Write-Output "(second sample)"
foreach ($f in Get-ChildItem 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\chrome.dll*' -ErrorAction SilentlyContinue) {
    Write-Output ($f.Name + " " + $f.Length + " " + $f.LastWriteTime)
}
