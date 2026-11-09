Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'paani\.exe|chrome\.exe' -and $_.CommandLine -match 'out' } |
  Select-Object ProcessId, Name, CreationDate, @{n='Cmd';e={$_.CommandLine.Substring(0,120)}} |
  Format-List
Write-Output "---- total browser procs ----"
(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'paani\.exe|chrome\.exe' }).Count
