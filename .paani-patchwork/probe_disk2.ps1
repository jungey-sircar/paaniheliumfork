$a = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk |
    Where-Object { $_.Name -ne '_Total' } |
    Select-Object Name, ReadBytesPerSec, WriteBytesPerSec, CurrentDiskQueueDepth, PercentDiskTime
Start-Sleep -Seconds 10
$b = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk |
    Where-Object { $_.Name -ne '_Total' } |
    Select-Object Name, ReadBytesPerSec, WriteBytesPerSec, CurrentDiskQueueDepth, PercentDiskTime
Write-Output '--- t0 ---'
$a | ForEach-Object { Write-Output ('{0}  R={1:N0}/s  W={2:N0}/s  Q={3}  busy={4}%' -f $_.Name, $_.ReadBytesPerSec, $_.WriteBytesPerSec, $_.CurrentDiskQueueDepth, $_.PercentDiskTime) }
Write-Output '--- t1 (10s later) ---'
$b | ForEach-Object { Write-Output ('{0}  R={1:N0}/s  W={2:N0}/s  Q={3}  busy={4}%' -f $_.Name, $_.ReadBytesPerSec, $_.WriteBytesPerSec, $_.CurrentDiskQueueDepth, $_.PercentDiskTime) }
