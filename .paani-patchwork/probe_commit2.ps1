$ErrorActionPreference = 'Stop'
$c = Get-Counter -Counter '\Memory\Committed Bytes', '\Memory\Commit Limit', '\Memory\Available MBytes', '\Memory\Page Uses Page File(s)' -ErrorAction SilentlyContinue
foreach ($s in $c.CounterSamples) {
    Write-Output ($s.Path + ' = ' + [math]::Round($s.CookedValue / 1MB, 2))
}
$all = Get-Process
$sum = ($all | Measure-Object -Property PrivateMemorySize64 -Sum).Sum
Write-Output ('ALL-PROC private-bytes sum GB=' + [math]::Round($sum / 1GB, 2) + ' count=' + $all.Count)
