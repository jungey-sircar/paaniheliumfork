$ErrorActionPreference = 'Stop'
function Snap {
    $p = Get-Process -Name 'lld-link' -ErrorAction SilentlyContinue
    if (-not $p) { return $null }
    [pscustomobject]@{
        Pid      = $p.Id
        WS       = $p.WorkingSet64
        Priv     = $p.PrivateMemorySize64
        CPU      = $p.CPU
        ReadB    = $p.PagedMemorySize64
        Files    = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $p.Id)).ReadTransferCount
        Writes   = (Get-CimInstance Win32_Process -Filter ("ProcessId=" + $p.Id)).WriteTransferCount
    }
}
$a = Snap
if (-not $a) { Write-Output 'lld-link NOT RUNNING'; exit 0 }
Start-Sleep -Seconds 20
$b = Snap
Write-Output ('pid=' + $b.Pid + ' wsMB=' + [math]::Round($b.WS / 1MB) + ' privMB=' + [math]::Round($b.Priv / 1MB))
Write-Output ('CPUsec/20s=' + [math]::Round($b.CPU - $a.CPU, 2))
Write-Output ('readKB/20s=' + [math]::Round(($b.Files - $a.Files) / 1KB) + '  writeKB/20s=' + [math]::Round(($b.Writes - $a.Writes) / 1KB))
$dir = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
Get-ChildItem -Path $dir -Filter 'paani.dll*' | ForEach-Object {
    Write-Output ('FILE ' + $_.Name + ' MB=' + [math]::Round($_.Length / 1MB) + ' mtime=' + $_.LastWriteTime.ToString('HH:mm:ss'))
}
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('RAM freeGB=' + [math]::Round($os.FreePhysicalMemory / 1MB, 2))
