$ErrorActionPreference = 'Continue'
$samples = (Get-Counter '\PhysicalDisk(*)\Disk Queue Length', '\PhysicalDisk(*)\Disk Bytes/sec' -SampleInterval 2 -MaxSamples 2).CounterSamples
$rows = $samples |
    Where-Object { $_.InstanceName -notlike '*_*' } |
    Group-Object InstanceName |
    ForEach-Object {
        $name = $_.Name
        $q = ($_.Group | Where-Object { $_.Path -like '*queue length' } | Measure-Object CookedValue -Maximum).Maximum
        $b = ($_.Group | Where-Object { $_.Path -like '*bytes/sec' } | Measure-Object CookedValue -Maximum).Maximum
        [pscustomobject]@{ Disk = $name; Queue = [math]::Round($q, 1); MBps = [math]::Round($b / 1MB, 1) }
    }
$rows | Format-Table -AutoSize
