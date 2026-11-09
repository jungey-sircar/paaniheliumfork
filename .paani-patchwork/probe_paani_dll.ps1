$ErrorActionPreference = 'Stop'
$path = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.dll.tmpc166338'
$p0 = Get-Process -Name 'lld-link' -ErrorAction SilentlyContinue
$s0 = (Get-Item $path -ErrorAction SilentlyContinue).Length
$c0 = if ($p0) { ($p0 | Measure-Object -Property CPU -Sum).Sum } else { 0 }
Start-Sleep -Seconds 20
$p1 = Get-Process -Name 'lld-link' -ErrorAction SilentlyContinue
$s1 = (Get-Item $path -ErrorAction SilentlyContinue).Length
$c1 = if ($p1) { ($p1 | Measure-Object -Property CPU -Sum).Sum } else { 0 }
Write-Output ('lld running=' + [bool]$p1 + ' wsMB=' + $(if ($p1) { [math]::Round(($p1 | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB) } else { 0 }))
Write-Output ('CPUsec delta over 20s=' + [math]::Round($c1 - $c0, 1))
Write-Output ('size delta MB=' + [math]::Round(($s1 - $s0) / 1MB, 1) + ' nowMB=' + [math]::Round($s1 / 1MB, 0))
$dll = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.dll'
Write-Output ('final paani.dll exists=' + (Test-Path $dll))
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('RAM freeGB=' + [math]::Round($os.FreePhysicalMemory / 1MB, 2))
