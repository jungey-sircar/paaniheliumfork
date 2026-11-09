$targets = @(10592, 5792, 18468, 9660)
foreach ($t in $targets) {
  $p = Get-Process -Id $t -ErrorAction SilentlyContinue
  if ($p) {
    '{0} {1} -> killing' -f $t, $p.ProcessName
    Stop-Process -Id $t -Force -ErrorAction SilentlyContinue
  } else {
    '{0} already gone' -f $t
  }
}
Start-Sleep -Seconds 2
'remaining:'
Get-Process siso, python, powershell -ErrorAction SilentlyContinue | Select-Object Id, ProcessName | Format-Table -AutoSize | Out-String -Width 120
