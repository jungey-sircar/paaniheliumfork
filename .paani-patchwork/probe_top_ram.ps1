$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('RAM freeGB=' + [math]::Round($os.FreePhysicalMemory / 1MB, 2))
$top = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12
foreach ($p in $top) {
    Write-Output ('RAM ' + [string]::Format('{0,6:N0} MB', ($p.WorkingSet64 / 1MB)) + '  COMMIT ' + [string]::Format('{0,6:N0} MB', ($p.PrivateMemorySize64 / 1MB)) + '  ' + $p.ProcessName + ' pid=' + $p.Id)
}
