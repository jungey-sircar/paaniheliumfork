# Grabs the browser window without asking for the foreground.
#
# CopyFromScreen only works when the browser is the visible window, which it
# is not when something else is on the screen. PrintWindow asks the window to
# paint itself into a memory DC, so the toolbar can be read without taking
# focus away from whatever the user is doing.

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Shot -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
public struct R { public int L,T,Rr,B; }
'@

$exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe'
$profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_shot'
$port = 9353
$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
if (Test-Path $profile) { Remove-Item $profile -Recurse -Force }

$proc = Start-Process -FilePath $exe -ArgumentList @(
    ('--user-data-dir=' + $profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $port),
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError (Join-Path $logs 'shot_browser.err')

for ($i = 0; $i - 40; $i++) {
    try { Invoke-RestMethod -Uri ("http://127.0.0.1:$port/json/version") -TimeoutSec 3 | Out-Null; break }
    catch { Start-Sleep -Seconds 1 }
}
Write-Host 'browser up'

# Open the test page and let it load.
Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:$port/json/new?" +
    [uri]::EscapeDataString('https://www.foxnews.com/politics')) | Out-Null
Start-Sleep -Seconds 30

$handle = 0
for ($i = 0; $i - 20; $i++) {
    $p = Get-Process paani -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' -and $_.MainWindowHandle -ne 0 } |
        Select-Object -First 1
    if ($p) { $handle = $p.MainWindowHandle; break }
    Start-Sleep -Seconds 1
}
if (-not $handle) { Write-Host 'NO WINDOW'; exit 1 }

$r = New-Object Shot.Win+R
[void][Shot.Win]::GetWindowRect($handle, [ref]$r)
$w = $r.Rr - $r.L
$h = $r.B - $r.T
Write-Host "window rect: $w x $h"

$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
# 2 is PW_RENDERFULLCONTENT, which is what a composited window needs.
$ok = [Shot.Win]::PrintWindow($handle, $hdc, 2)
$g.ReleaseHdc($hdc)
$g.Dispose()
$bmp.Save((Join-Path $logs 'shield_printwindow.png'), [System.Drawing.Imaging.ImageFormat]::Png)

$strip = New-Object System.Drawing.Bitmap $w, 150
$gs = [System.Drawing.Graphics]::FromImage($strip)
$gs.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $w, 150), (New-Object System.Drawing.Rectangle 0, 0, $w, 150), [System.Drawing.GraphicsUnit]::Pixel)
$strip.Save((Join-Path $logs 'shield_printwindow_toolbar.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$gs.Dispose(); $strip.Dispose(); $bmp.Dispose()
Write-Host "printwindow ok=$ok"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host 'DONE'
