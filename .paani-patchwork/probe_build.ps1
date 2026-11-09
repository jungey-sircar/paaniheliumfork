$ErrorActionPreference = 'SilentlyContinue'

foreach ($p in Get-CimInstance Win32_Process -Filter "name='python.exe'") {
    Write-Output ("PID=" + $p.ProcessId + " :: " + $p.CommandLine)
}
foreach ($s in Get-CimInstance Win32_Process -Filter "name='siso.exe'") {
    Write-Output ("SISO PID=" + $s.ProcessId)
}
Write-Output ("CPU%=" + (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter 'Name="_Total"').PercentProcessorTime)
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("FreePhysGB=" + [math]::Round($os.FreePhysicalMemory / 1MB, 1))
$clang = @(Get-Process clang-cl -ErrorAction SilentlyContinue)
Write-Output ("clang-cl procs=" + $clang.Count)
