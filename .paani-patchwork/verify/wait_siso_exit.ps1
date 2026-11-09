$ErrorActionPreference = 'Continue'
$log = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\siso_wait.txt'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $log
for ($i = 0; $i -lt 120; $i++) {
  $p = Get-Process -Id 19244 -ErrorAction SilentlyContinue
  if ($null -eq $p) {
    "SISO EXITED $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
    break
  }
  Start-Sleep -Seconds 20
}
$still = Get-Process -Id 19244 -ErrorAction SilentlyContinue
if ($null -ne $still) {
  "STILL RUNNING after loop $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
}
