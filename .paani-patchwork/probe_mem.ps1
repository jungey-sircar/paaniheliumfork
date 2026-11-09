$ErrorActionPreference = 'SilentlyContinue'

Write-Output "--- top 12 by working set (MB) ---"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12 |
    ForEach-Object {
        Write-Output ("  " + $_.ProcessName + " pid=" + $_.Id +
            " ws=" + [math]::Round($_.WorkingSet64 / 1MB, 0) +
            " priv=" + [math]::Round($_.PrivateMemorySize64 / 1MB, 0))
    }

$os = Get-CimInstance Win32_OperatingSystem
Write-Output ("FreePhysGB=" + [math]::Round($os.FreePhysicalMemory / 1MB, 1))
Write-Output ("CommitFreeGB=" + [math]::Round($os.FreeVirtualMemory / 1MB, 1))
Write-Output ("CommitLimitGB=" + [math]::Round($os.TotalVirtualMemorySize / 1MB, 1))

Write-Output "--- total private bytes by process name (top 8, GB) ---"
Get-Process | Group-Object ProcessName | ForEach-Object {
    $sum = ($_.Group | Measure-Object PrivateMemorySize64 -Sum).Sum / 1GB
    [PSCustomObject]@{ Name = $_.Name; GB = [math]::Round($sum, 2) }
} | Sort-Object GB -Descending | Select-Object -First 8 |
    ForEach-Object { Write-Output ("  " + $_.Name + " = " + $_.GB + " GB") }
