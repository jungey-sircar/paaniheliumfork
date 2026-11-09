$s1 = Get-Counter -Counter '\PhysicalDisk(*)\Disk Read Bytes/sec' -SampleInterval 1 -MaxSamples 1
$names = $s1.CounterSamples | ForEach-Object { ($_.Path -split '\\')[1] } | Sort-Object -Unique
Write-Output ('INSTANCES: ' + ($names -join ' | '))
$c = @()
foreach ($n in $names) {
    $c += "\PhysicalDisk($n)\Disk Read Bytes/sec"
    $c += "\PhysicalDisk($n)\Disk Write Bytes/sec"
    $c += "\PhysicalDisk($n)\Current Disk Queue Length"
}
$sc = Get-Counter -Counter $c -SampleInterval 3 -MaxSamples 4 -ErrorAction SilentlyContinue
foreach ($s in $sc) {
    $parts = @()
    foreach ($cs in $s.CounterSamples) {
        $n = ($cs.Path -split '\\')[2]
        $m = ($cs.Path -split '\\')[-1]
        $v = if ($m -eq 'current disk queue length') { [math]::Round($cs.CookedValue, 1) } else { [math]::Round($cs.CookedValue / 1MB, 1) }
        if ($v -gt 0) { $parts += ('{0} {1}={2}' -f $n, $m, $v) }
    }
    Write-Output ($s.Timestamp.ToString('HH:mm:ss') + '  ' + ($parts -join '  '))
}
