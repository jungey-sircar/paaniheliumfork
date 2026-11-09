$p = Get-Process -Id 8708 -ErrorAction SilentlyContinue
if ($null -eq $p) {
  Write-Output "lld-link PID 8708 is GONE"
} else {
  Write-Output ("CPU_seconds={0} WS_MB={1} Start={2}" -f [math]::Round($p.CPU,1), [math]::Round($p.WorkingSet64/1MB,0), $p.StartTime.ToString('HH:mm:ss'))
}
Start-Sleep -Seconds 20
$p2 = Get-Process -Id 8708 -ErrorAction SilentlyContinue
if ($null -eq $p2) {
  Write-Output "lld-link PID 8708 is GONE after sleep"
} else {
  Write-Output ("CPU_seconds={0} WS_MB={1}" -f [math]::Round($p2.CPU,1), [math]::Round($p2.WorkingSet64/1MB,0))
}
Write-Output "=== paani.dll in out dir ==="
Get-ChildItem 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.dll' -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Output ("{0} {1} bytes" -f $_.LastWriteTime.ToString('MM-dd HH:mm:ss'), $_.Length) }
