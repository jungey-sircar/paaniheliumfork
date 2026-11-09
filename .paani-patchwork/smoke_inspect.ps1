$procs = Get-CimInstance Win32_Process -Filter "Name='chrome.exe'"
Write-Output ('chrome.exe process count = ' + @($procs).Count)
$treeTypes = $procs | ForEach-Object { if ($_.CommandLine -match '--type=([a-z-]+)') { $matches[1] } elseif ($_.CommandLine -match '--type=utility') { 'utility' } else { 'browser' } }
Write-Output ('types: ' + (($treeTypes | Group-Object | ForEach-Object { $_.Name + 'x' + $_.Count }) -join ' '))
$main = Get-Process -Id 14228 -ErrorAction SilentlyContinue
if ($main) {
    $memMB = [math]::Round((($procs | ForEach-Object { (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue).WorkingSet64 } | Measure-Object -Sum).Sum) / 1MB, 0)
    Write-Output ('tree working set = ' + $memMB + 'MB  main CPU=' + [math]::Round($main.CPU,1) + 's')
    $win = Get-Process -Id 14228 | Where-Object { $_.MainWindowTitle }
    Write-Output ('window title: ' + $(if ($win) { $win.MainWindowTitle } else { '(none yet)' }))
}
Write-Output '--- shutting the smoke instance down ---'
Stop-Process -Id 14228 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 6
$left = @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'").Count
Write-Output ('remaining chrome.exe = ' + $left)
if ($left -gt 0) { Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force; Start-Sleep -Seconds 5; Write-Output ('after sweep = ' + @(Get-CimInstance Win32_Process -Filter "Name='chrome.exe'").Count) }
