# Stops a leftover Chromium build so a new one can take the siso lock.
#
# siso has to go first, then the ninja driver, then any orphaned compiler
# children the driver left behind.
$ErrorActionPreference = 'Continue'

$ids = @(9244, 6984, 22480)
foreach ($id in $ids) {
    $p = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($p) {
        Write-Output ("KILLING {0} {1}" -f $p.Id, $p.ProcessName)
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 3

$left = Get-Process siso,ninja,autoninja,clang-cl,lld-link -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' }
if ($left) {
    foreach ($p in $left) {
        Write-Output ("STILL ALIVE {0} {1}" -f $p.Id, $p.ProcessName)
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

$still = Get-Process siso,ninja,autoninja -ErrorAction SilentlyContinue
if ($still) {
    foreach ($p in $still) { Write-Output ("REMAINS {0} {1}" -f $p.Id, $p.ProcessName) }
    exit 1
}
Write-Output 'BUILD SLOTS FREE'
