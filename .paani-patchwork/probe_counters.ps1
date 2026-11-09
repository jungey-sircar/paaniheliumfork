$c = @(
    '\Process(lld-link)\IO Write Bytes/sec',
    '\Process(lld-link)\IO Read Bytes/sec',
    '\Process(lld-link)\Page Faults/sec',
    '\Process(lld-link)\% Privileged Time',
    '\Process(lld-link)\Working Set - Private',
    '\Memory\Pages Input/sec'
)
$s = Get-Counter -Counter $c -SampleInterval 2 -MaxSamples 6
foreach ($sample in $s) {
    $t = $sample.Timestamp.ToString('HH:mm:ss')
    $row = ($sample.CounterSamples | ForEach-Object {
        $n = ($_.Path -split '\\')[-1]
        '{0}={1:N0}' -f $n, $_.CookedValue
    }) -join '  '
    Write-Output ($t + ' ' + $row)
    Start-Sleep -Milliseconds 200
}
