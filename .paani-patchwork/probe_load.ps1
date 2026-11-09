$ErrorActionPreference = 'SilentlyContinue'

$cpu = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter 'Name="_Total"').PercentProcessorTime
Write-Output ("CPU%=" + $cpu)

$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("FreePhysGB=" + [math]::Round($os.FreePhysicalMemory / 1MB, 1))
Write-Output ("TotalPhysGB=" + [math]::Round($os.TotalVisibleMemorySize / 1MB, 1))
Write-Output ("CommitFreeGB=" + [math]::Round($os.FreeVirtualMemory / 1MB, 1))
Write-Output ("CommitLimitGB=" + [math]::Round($os.TotalVirtualMemorySize / 1MB, 1))

foreach ($pf in Get-CimInstance Win32_PageFileUsage) {
    Write-Output ("PageFile=" + $pf.Name + " AllocMB=" + $pf.AllocatedSizeMB + " PeakMB=" + $pf.PeakUsageMB)
}

$procs = Get-Process | Where-Object { $_.ProcessName -match 'clang|link|rustc|node|siso|python' }
Write-Output ("BuilderProcs=" + $procs.Count)
$rss = ($procs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1GB
Write-Output ("BuilderRSS_GB=" + [math]::Round($rss, 2))

Write-Output "Top memory consumers:"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 6 |
    ForEach-Object { Write-Output ("  " + $_.ProcessName + " " + [math]::Round($_.WorkingSet64 / 1MB, 0) + "MB") }
