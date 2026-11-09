$ErrorActionPreference = 'Continue'
Get-Process lld-link, link, siso -ErrorAction SilentlyContinue |
  Select-Object Id, ProcessName,
    @{n = 'CPU_s'; e = { [math]::Round($_.CPU, 0) } },
    @{n = 'RAM_GB'; e = { [math]::Round($_.WorkingSet64 / 1GB, 2) } },
    @{n = 'Priv_GB'; e = { [math]::Round($_.PrivateMemorySize64 / 1GB, 2) } } |
  Format-Table -AutoSize | Out-String -Width 140
$os = Get-CimInstance Win32_OperatingSystem
'free physical GB: ' + [math]::Round($os.FreePhysicalMemory / 1MB, 1)
'total physical GB: ' + [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
'commit free GB: ' + [math]::Round(($os.TotalVirtualMemorySize - $os.FreeVirtualMemory) / 1MB, 1) + ' used of ' + [math]::Round($os.TotalVirtualMemorySize / 1MB, 1)
$exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.dll'
if (Test-Path $exe) {
  $i = Get-Item $exe
  'paani.dll ' + [math]::Round($i.Length / 1MB, 1) + ' MB mtime ' + $i.LastWriteTime.ToString('o')
} else { 'paani.dll not yet written' }
'now: ' + (Get-Date -Format o)
