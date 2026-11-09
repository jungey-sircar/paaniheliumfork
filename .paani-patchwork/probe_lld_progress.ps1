$cnt = @('\Process(lld-link)\Page Reads/sec', '\Process(lld-link)\IO Other Bytes/sec')
for ($i = 0; $i -lt 6; $i++) {
    $p = Get-Process -Id 1148 -ErrorAction SilentlyContinue
    if (-not $p) { Write-Output 'lld-link EXITED'; break }
    $cs = (Get-Counter -Counter $cnt -SampleInterval 5 -MaxSamples 1 -ErrorAction SilentlyContinue).CounterSamples
    $pr = ($cs | Where-Object { $_.Path -match 'Page Reads' }).CookedValue
    $ob = ($cs | Where-Object { $_.Path -match 'IO Other' }).CookedValue
    $os = Get-CimInstance Win32_OperatingSystem
    Write-Output ('{0}  WS={1:N0}MB Priv={2:N0}MB CPU={3:N1}s PageReads/s={4:N0} IOOther/s={5:N1} FreePhys={6:N2}GB' -f (Get-Date).ToString('HH:mm:ss'), ($p.WorkingSet64/1MB), ($p.PrivateMemorySize64/1MB), $p.CPU, $pr, $ob, ($os.FreePhysicalMemory*1KB/1GB))
    Start-Sleep -Seconds 25
}
