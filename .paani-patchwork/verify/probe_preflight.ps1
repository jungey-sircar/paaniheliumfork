$ErrorActionPreference = 'Continue'
'=== processes ==='
Get-Process cl, link, lld-link, siso, python, powershell -ErrorAction SilentlyContinue |
  Select-Object Id, ProcessName, @{n='CPU';e={[math]::Round($_.CPU,1)}}, @{n='WS_MB';e={[math]::Round($_.WorkingSet64/1MB)}}, StartTime |
  Sort-Object ProcessName, Id |
  Format-Table -AutoSize | Out-String -Width 220
'=== newest obj under frame ==='
$frame = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\obj\chrome\browser\ui\views\frame'
Get-ChildItem $frame -Recurse -Filter '*.obj' -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 8 Name, LastWriteTime |
  Format-Table -AutoSize | Out-String -Width 220
'=== backdrop dirs ==='
Get-ChildItem $frame -Directory -Filter 'paani_*' -ErrorAction SilentlyContinue | Select-Object FullName | Out-String -Width 220
'=== siso dirs in out ==='
Get-ChildItem 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default' -Filter '*.siso*' -ErrorAction SilentlyContinue |
  Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize | Out-String -Width 220
'=== disk queue ==='
(Get-Counter '\PhysicalDisk(_Total)\% Disk Time' -ErrorAction SilentlyContinue).CounterSamples.CookedValue
'now: ' + (Get-Date -Format o)
