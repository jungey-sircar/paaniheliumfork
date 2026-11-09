$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$limitGB = [math]::Round($os.TotalVirtualMemorySize / 1MB, 2)
$freeGB = [math]::Round($os.FreeCommitSpace / 1MB, 2)
Write-Output ("COMMIT limitGB=" + $limitGB + " freeGB=" + $freeGB + " chargeGB=" + [math]::Round(($limitGB - $freeGB), 2))
$cs = Get-CimInstance Win32_ComputerSystem
Write-Output ("PAGEFILE automatic=" + $cs.AutomaticManagedPagefile)
Get-CimInstance Win32_PageFileSetting | ForEach-Object {
    Write-Output ("SETTING " + $_.Name + " initialMB=" + $_.InitialSize + " maxMB=" + $_.MaximumSize)
}
Get-CimInstance Win32_PageFileUsage | ForEach-Object {
    Write-Output ("USAGE " + $_.Name + " allocMB=" + $_.AllocatedBaseSize + " curMB=" + $_.CurrentUsage + " peakMB=" + $_.PeakUsage)
}
