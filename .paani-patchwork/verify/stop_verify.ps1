param([int]$BrowserPid, [int]$ServerPid)
$ErrorActionPreference = 'SilentlyContinue'
foreach ($target in @($BrowserPid, $ServerPid)) {
    if ($target -gt 0) {
        taskkill /PID $target /T /F | Out-Null
        Write-Output ('KILLED ' + $target)
    }
}
Start-Sleep -Seconds 3
$left = Get-Process paani, python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -gt (Get-Date).AddMinutes(-15) }
foreach ($p in $left) { Write-Output ('STILL-RUNNING ' + $p.ProcessName + ' ' + $p.Id) }
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('RAM freeGB=' + [math]::Round($os.FreePhysicalMemory / 1MB, 2))
