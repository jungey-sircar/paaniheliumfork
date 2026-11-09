$ErrorActionPreference = 'SilentlyContinue'

function Snapshot {
    $p = Get-Process -Id 1148
    if (-not $p) { Write-Output "lld-link GONE"; return $null }
    $re = (Get-CimInstance Win32_Process -Filter "ProcessId=1148").ReadTransferCount
    $wr = (Get-CimInstance Win32_Process -Filter "ProcessId=1148").WriteTransferCount
    return [PSCustomObject]@{
        CPU = [math]::Round($p.CPU, 1)
        WS_MB = [math]::Round($p.WorkingSet64 / 1MB, 0)
        ReadKB = [math]::Round($re / 1024, 0)
        WriteKB = [math]::Round($wr / 1024, 0)
    }
}

$a = Snapshot
if ($a) {
    Write-Output ("t0: CPU=" + $a.CPU + " WS_MB=" + $a.WS_MB + " ReadKB=" + $a.ReadKB + " WriteKB=" + $a.WriteKB)
    Start-Sleep -Seconds 60
    $b = Snapshot
    if ($b) {
        Write-Output ("t1: CPU=" + $b.CPU + " WS_MB=" + $b.WS_MB + " ReadKB=" + $b.ReadKB + " WriteKB=" + $b.WriteKB)
        Write-Output ("DELTA: CPUsec=" + [math]::Round($b.CPU - $a.CPU, 1) +
            " ReadKB=" + ($b.ReadKB - $a.ReadKB) + " WriteKB=" + ($b.WriteKB - $a.WriteKB))
    }
}
