$procs = Get-CimInstance Win32_Process -Filter "Name='lld-link.exe'"
foreach ($p in $procs) {
    $o = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    $cmdline = $p.CommandLine
    $tail = if ($cmdline) { $cmdline.Substring([Math]::Max(0, $cmdline.Length - 220)) } else { '(n/a)' }
    Write-Output ('PID=' + $p.ProcessId +
        ' Start=' + $p.CreationDate.ToString('HH:mm:ss') +
        ' CPUsec=' + [math]::Round($o.CPU, 1) +
        ' WS_MB=' + [math]::Round($o.WorkingSet64 / 1MB, 0) +
        ' Priv_MB=' + [math]::Round($o.PrivateMemorySize64 / 1MB, 0) +
        ' Threads=' + $o.Threads.Count)
    Write-Output ('  CMD...=' + $tail)
}
if (-not $procs) { Write-Output 'NO lld-link RUNNING' }
