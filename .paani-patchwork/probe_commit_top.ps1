$ErrorActionPreference = 'Stop'
$procs = Get-Process | Where-Object { $_.PrivateMemorySize64 -gt 200MB }
$total = 0
foreach ($p in $procs) {
    $total += $p.PrivateMemorySize64
}
Write-Output ('SUM of listed GB=' + [math]::Round($total / 1GB, 2))
$procs | Sort-Object PrivateMemorySize64 -Descending | Select-Object -First 15 | ForEach-Object {
    Write-Output ('COMMIT ' + [string]::Format('{0,8:N0} MB', ($_.PrivateMemorySize64 / 1MB)) + '  ' + $_.ProcessName + ' pid=' + $_.Id)
}
Write-Output '--- build tool leftovers ---'
Get-Process | Where-Object { $_.ProcessName -match 'lld|link|clang|ninja|siso|cpu_proxy|metaroot' } | ForEach-Object {
    Write-Output ('LEFT ' + $_.ProcessName + ' pid=' + $_.Id + ' commitMB=' + [math]::Round($_.PrivateMemorySize64 / 1MB) + ' start=' + $_.StartTime)
}
