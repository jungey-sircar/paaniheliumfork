param([int]$Seconds = 10)
$ErrorActionPreference = 'Continue'

function Snap {
    $p = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    return [pscustomobject]@{
        Cpu = $p.CPU
        Read = $p.IOReadBytes
        Write = $p.IOWriteBytes
        Ws = $p.WorkingSet64
    }
}

$a = Snap
Start-Sleep -Seconds $Seconds
$b = Snap
if (-not $a -or -not $b) { Write-Output 'process gone'; exit 1 }

Write-Output ("cpu   +{0:N1} s" -f ($b.Cpu - $a.Cpu))
Write-Output ("read  +{0:N1} MB" -f (($b.Read - $a.Read) / 1MB))
Write-Output ("write +{0:N1} MB" -f (($b.Write - $a.Write) / 1MB))
Write-Output ("ws    {0:N1} GB" -f ($b.Ws / 1GB))
