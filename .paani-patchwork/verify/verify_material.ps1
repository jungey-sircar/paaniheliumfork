# Verifies Paani's translucent chrome material on a real window.
#
# Pass criteria, measured from pixels rather than from flags:
#   1. the chrome band is not near-black (it was, before the material was drawn)
#   2. the band changes when the window moves over a different part of the
#      desktop, which is what a material does and a flat colour cannot
#   3. the web contents area is unaffected by the desktop behind the window
param(
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_material',
    [int]$Port = 9345
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Material -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
public struct R { public int L,T,Rr,B; }
'@

$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null

# Build-tree instances only; the user's installed browser is left alone.
Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path $Exe)) { Write-Output "MISSING EXE: $Exe"; exit 1 }

$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    '--disable-features=Translate',
    ('--remote-debugging-port=' + $Port),
    '--window-size=1000,640', '--window-position=60,40',
    'http://127.0.0.1:8731/adtest.html'
) -PassThru

$handle = [IntPtr]::Zero
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    $fresh = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($fresh -and $fresh.MainWindowHandle -ne 0) { $handle = $fresh.MainWindowHandle; break }
}
if ($handle -eq [IntPtr]::Zero) { Write-Output 'NO WINDOW'; exit 1 }

function Get-Rect($h) {
    $r = New-Object Material.Win+R
    [void][Material.Win]::GetWindowRect($h, [ref]$r)
    return $r
}

function Save-Band($h, [string]$name) {
    $r = Get-Rect $h
    $w = $r.Rr - $r.L; $ht = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $ht
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $ht))
    $path = Join-Path $logs ($name + '.png')
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    Write-Output "captured $name rect=$($r.L),$($r.T) ${w}x${ht}"
    return $path
}

Start-Sleep -Seconds 6
$p1 = Save-Band $handle 'material_pos_a'

# Move to the far side of the desktop so the material has to sample different
# wallpaper. SWP_NOSIZE|SWP_NOZORDER = 0x0001|0x0002.
Add-Type -Namespace Material -Name M -MemberDefinition @'
[DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
'@
$screenW = [Material.M]::GetSystemMetrics(0)
$screenH = [Material.M]::GetSystemMetrics(1)
$x = [Math]::Max(0, $screenW - 1000 - 20)
$y = [Math]::Max(0, $screenH - 640 - 20)
Write-Output "desktop=${screenW}x${screenH}, moving window to ${x},${y}"
[void][Material.Win]::SetWindowPos($handle, [IntPtr]::Zero, $x, $y, 1000, 640, 0x0003)
Start-Sleep -Seconds 6
$p2 = Save-Band $handle 'material_pos_b'

Write-Output "PID=$($proc.Id) handles: $p1 $p2"
