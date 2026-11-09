$ErrorActionPreference = 'SilentlyContinue'

foreach ($n in @('link', 'lld', 'chrome', 'siso')) {
    foreach ($p in Get-Process $n -ErrorAction SilentlyContinue) {
        Write-Output ($n + " PID=" + $p.Id +
            " CPUsec=" + [math]::Round($p.CPU, 1) +
            " WS_MB=" + [math]::Round($p.WorkingSet64 / 1MB, 0) +
            " Priv_MB=" + [math]::Round($p.PrivateMemorySize64 / 1MB, 0))
    }
}

$cpu = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter 'Name="_Total"').PercentProcessorTime
Write-Output ("CPU%=" + $cpu)

$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("FreePhysGB=" + [math]::Round($os.FreePhysicalMemory / 1MB, 1))

$disk = Get-Counter '\PhysicalDisk(0 C:)\Disk Time', '\Memory\Pages/sec' -ErrorAction SilentlyContinue
foreach ($s in $disk.CounterSamples) {
    Write-Output ($s.Path + " = " + [math]::Round($s.CookedValue, 1))
}
