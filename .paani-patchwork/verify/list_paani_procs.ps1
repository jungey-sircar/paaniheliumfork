Get-CimInstance Win32_Process -Filter "Name='paani.exe'" |
  Select-Object ProcessId, CreationDate, @{n='CmdLine';e={$_.CommandLine}} |
  Format-List
