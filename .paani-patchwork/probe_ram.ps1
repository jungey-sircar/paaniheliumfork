$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$total = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$commit = [math]::Round($os.FreeCommitSpace / 1MB, 2)
Write-Output ("RAM freeGB=" + $free + " / " + $total + "  commitFreeGB=" + $commit)
$busy = Get-Process | Where-Object { $_.ProcessName -match 'siso|ninja|lld-link|clang-cl|python' }
if ($busy) {
    $busy | ForEach-Object { Write-Output ("RUNNING " + $_.ProcessName + " pid=" + $_.Id + " rssMB=" + [math]::Round($_.WorkingSet64 / 1MB)) }
} else {
    Write-Output 'RUNNING none'
}
$top = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 6
$top | ForEach-Object { Write-Output ("TOP " + $_.ProcessName + " " + [math]::Round($_.WorkingSet64 / 1MB) + "MB") }
