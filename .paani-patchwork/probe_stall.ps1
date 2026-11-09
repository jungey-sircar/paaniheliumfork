$ErrorActionPreference = 'Stop'
$set = '\Memory\Page Reads/sec', '\Memory\Page Writes/sec', '\Memory\Pages/sec', '\PhysicalDisk(0 C:)\% Idle Time', '\PhysicalDisk(1 E:)\% Idle Time', '\Processor(_Total)\% Processor Time'
$c = Get-Counter -Counter $set -SampleInterval 3 -MaxSamples 3 -ErrorAction SilentlyContinue
foreach ($s in $c) {
    foreach ($samp in $s.CounterSamples) {
        Write-Output ($samp.Path + ' = ' + [math]::Round($samp.CookedValue, 1))
    }
    Write-Output '---'
}
$p = Get-Process -Name 'lld-link' -ErrorAction SilentlyContinue
if ($p) {
    Write-Output ('lld threads=' + $p.Threads.Count + ' handles=' + $p.HandleCount + ' responded=' + $p.Responding)
} else {
    Write-Output 'lld-link GONE'
}
