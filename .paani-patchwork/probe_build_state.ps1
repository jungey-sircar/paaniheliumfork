$ErrorActionPreference = 'SilentlyContinue'
Write-Output ('NOW: ' + (Get-Date -Format 'HH:mm:ss'))
$procs = Get-Process | Where-Object ProcessName -match 'lld|clang|siso|ninja' |
    Sort-Object CPU -Descending
Write-Output ('BUILD PROCS: ' + $procs.Count)
$procs | Select-Object -First 10 ProcessName, Id,
    @{n='CPU_s'; e={ [math]::Round($_.CPU, 1) } },
    @{n='WS_MB'; e={ [math]::Round($_.WorkingSet64 / 1MB, 0) } } |
    Format-Table -AutoSize | Out-String -Width 120 | Write-Output

$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('FREE_PHYS_MB: ' + [math]::Round($os.FreePhysicalMemory / 1KB, 0))
Write-Output ('TOTAL_PHYS_MB: ' + [math]::Round($os.TotalPhysicalMemory / 1KB, 0))
$counters = (Get-Counter '\Memory\Committed Bytes', '\Memory\Commit Limit', '\Memory\Available MBytes',
    '\Processor(_Total)\% Processor Time', '\PhysicalDisk(_Total)\% Disk Time',
    '\Paging File(_Total)\% Usage' -ErrorAction SilentlyContinue).CounterSamples
foreach ($c in $counters) {
    Write-Output ($c.Path + ' = ' + [math]::Round($c.CookedValue, 1))
}
Write-Output 'TOP RAM (non-build):'
Get-Process | Where-Object ProcessName -notmatch 'lld|clang|siso|ninja' |
    Sort-Object WorkingSet64 -Descending | Select-Object -First 8 ProcessName, Id,
    @{n='WS_MB'; e={ [math]::Round($_.WorkingSet64 / 1MB, 0) } } |
    Format-Table -AutoSize | Out-String -Width 120 | Write-Output
