# Captures the New Tab Page of a fresh Paani profile.
#
# The browser's own window is asked to paint itself with PrintWindow, so
# nothing on the desktop has to be uncovered and no focus is taken away.

param(
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_ntp',
    [int]$Port = 9356,
    [string]$Out = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\ntp_paani.png'
)

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Ntp -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
public struct R { public int L,T,Rr,B; }
'@

$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
if (Test-Path $Profile) { Remove-Item $Profile -Recurse -Force }

$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $Port),
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError (Join-Path $logs 'ntp_browser.err')

for ($i = 0; $i - 40; $i++) {
    try { Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/version") -TimeoutSec 3 | Out-Null; break }
    catch { Start-Sleep -Seconds 1 }
}
Write-Host 'browser up'

# The first tab of a fresh profile is the New Tab Page; give it time to settle.
Start-Sleep -Seconds 18
try {
    $targets = Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/list") -TimeoutSec 5
    Write-Host ('targets: ' + (($targets | ForEach-Object { $_.url }) -join ' | '))
} catch {
    Write-Host 'no target list'
}

$handle = 0
for ($i = 0; $i - 20; $i++) {
    $p = Get-Process paani -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' -and $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1
    if ($p) { $handle = $p.MainWindowHandle; break }
    Start-Sleep -Seconds 1
}
if (-not $handle) { Write-Host 'NO WINDOW'; exit 1 }

$r = New-Object Ntp.Win+R
[void][Ntp.Win]::GetWindowRect($handle, [ref]$r)
$w = $r.Rr - $r.L
$h = $r.B - $r.T
Write-Host "window rect: $w x $h"

$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
$ok = [Ntp.Win]::PrintWindow($handle, $hdc, 2)
$g.ReleaseHdc($hdc)
$g.Dispose()
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Host "printwindow ok=$ok -> $Out"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host 'DONE'
