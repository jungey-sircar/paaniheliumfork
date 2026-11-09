$names = 'lld-link', 'link', 'chrome', 'action', 'python', 'node', 'siso', 'ccache', 'sccache', 'rc', 'llvm-rc', 'mt', 'powershell'
$all = Get-CimInstance Win32_Process | Where-Object { $_.Name -notmatch '^(svchost|System|Idle|csrss|wininit|winlogon|services|lsass|smss)' }
$busy = $all | ForEach-Object {
    $o = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
    if ($o) { [PSCustomObject]@{ Name = $_.Name; PID = $_.ProcessId; CPU = [math]::Round($o.CPU, 0); WS_MB = [math]::Round($o.WorkingSet64 / 1MB, 0) } }
}
Write-Output '--- top 12 by CPU ---'
$busy | Sort-Object CPU -Descending | Select-Object -First 12 | Format-Table -AutoSize | Out-String -Width 120 | Write-Output
Write-Output '--- linkers/tools ---'
$busy | Where-Object { $_.Name -match '(?i)lld|link|rc\.exe|siso|sccache|action|chrome_' } | Format-Table -AutoSize | Out-String -Width 120 | Write-Output
