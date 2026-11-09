$ErrorActionPreference = 'Continue'
Get-CimInstance Win32_Process -Filter "Name='python.exe' or Name='siso.exe' or Name='powershell.exe' or Name='cl.exe'" |
  Select-Object ProcessId, CreationDate, Name, @{n='cmd';e={$_.CommandLine}} |
  Sort-Object CreationDate |
  ForEach-Object { '{0} {1} [{2}] {3}' -f $_.CreationDate, $_.ProcessId, $_.Name, $_.cmd }
