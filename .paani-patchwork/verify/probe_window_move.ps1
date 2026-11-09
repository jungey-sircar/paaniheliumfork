# Probes how the built window can be positioned at all.
#
# verify_material2.ps1 found that SetWindowPos returns success while the window
# stays exactly where it was, so the options have to be measured rather than
# assumed: a position given on the command line at launch, a move after launch,
# and a move of a window that was told where to start.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Probe -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int cx, int cy, bool repaint);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
[DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
[DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
public struct R { public int L,T,Rr,B; }
'@

$exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe'
$profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_probe'
$port = 9347

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

function Rect($h) {
    $r = New-Object Probe.Win+R
    [void][Probe.Win]::GetWindowRect($h, [ref]$r)
    return "$($r.L),$($r.T) $($r.Rr - $r.L)x$($r.B - $r.T)"
}

Write-Host "primary screen = $([Probe.Win]::GetSystemMetrics(0))x$([Probe.Win]::GetSystemMetrics(1))"

$proc = Start-Process -FilePath $exe -ArgumentList @(
    ('--user-data-dir=' + $profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $port),
    '--window-size=1000,640', '--window-position=900,300',
    'http://127.0.0.1:8731/adtest.html'
) -PassThru

$h = [IntPtr]::Zero
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($p -and $p.MainWindowHandle -ne 0) { $h = $p.MainWindowHandle; break }
}
if ($h -eq [IntPtr]::Zero) { Write-Host 'NO WINDOW'; exit 1 }

Write-Host "dpi for window = $([Probe.Win]::GetDpiForWindow($h)), zoomed = $([Probe.Win]::IsZoomed($h))"
Write-Host "launch position --window-position=900,300 gave rect $(Rect $h)"

$ok = [Probe.Win]::SetWindowPos($h, [IntPtr]::Zero, 300, 100, 1000, 640, 0x0002)
Start-Sleep -Milliseconds 1500
Write-Host "SetWindowPos ok=$ok -> rect $(Rect $h)"

$ok2 = [Probe.Win]::MoveWindow($h, 300, 100, 1000, 640, $true)
Start-Sleep -Milliseconds 1500
Write-Host "MoveWindow ok=$ok2 -> rect $(Rect $h)"

Start-Sleep -Seconds 3
Write-Host "after a wait -> rect $(Rect $h)"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
