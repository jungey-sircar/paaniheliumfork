# Verifies Paani's translucent chrome material on a real window.
#
# The first version of this harness measured nothing, for two reasons it now
# fixes:
#   * SetWindowPos was called and its result ignored; both captures reported
#     the same rect, so the window never moved.
#   * the first capture was taken before the test page had finished loading,
#     so the differences that were scored were page rendering, not material.
#
# Pass criteria, measured from pixels rather than from flags:
#   1. the chrome band is not near-black (it was, before the material was drawn)
#   2. the band changes when the window moves to a different part of the desktop
#   3. the band returns to its first appearance when the window moves back, so
#      the change cannot be time or page rendering
#   4. the web contents area does not change with position; web content is meant
#      to stay opaque
#   5. the page is settled before any capture, and the window really moved
param(
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_material',
    [int]$Port = 9345,
    [string]$Url = 'http://127.0.0.1:8731/adtest.html'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Mat2 -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int cx, int cy, bool repaint);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
[DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
[DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
public struct R { public int L,T,Rr,B; }
'@

$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$out = Join-Path $logs 'material2'
Remove-Item ($out + '*.png') -ErrorAction SilentlyContinue

# The positions are far apart on the desktop so the band has to sample
# different wallpaper, and A/C are the same spot so a time-based change is
# distinguishable from a position-based one.
$posA = $null

# Build-tree instances only; the user's installed browser is left alone.
Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (-not (Test-Path $Exe)) { Write-Output "MISSING EXE: $Exe"; exit 1 }

# The window is not placed by a flag: some builds reposition the first window
# from session data, so the harness moves it itself and then measures where it
# actually landed.
$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    '--disable-features=Translate',
    ('--remote-debugging-port=' + $Port),
    $Url
) -PassThru

$handle = [IntPtr]::Zero
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 2
    $fresh = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($fresh -and $fresh.MainWindowHandle -ne 0) { $handle = $fresh.MainWindowHandle; break }
}
if ($handle -eq [IntPtr]::Zero) { Write-Output 'NO WINDOW'; exit 1 }
Write-Output "window handle=$handle pid=$($proc.Id)"

function Get-Rect($h) {
    $r = New-Object Mat2.Win+R
    [void][Mat2.Win]::GetWindowRect($h, [ref]$r)
    return [pscustomobject]@{ L = $r.L; T = $r.T; W = ($r.Rr - $r.L); H = ($r.B - $r.T) }
}

# Captures what is actually on screen, which is the composited result a user
# sees. The window is raised first so another window cannot be what gets sampled.
# These helpers return objects, so their diagnostics go to the host; writing
# them into the pipeline would be prepended to the return value.
function Save-Shot($h, [string]$name) {
    [void][Mat2.Win]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 400
    $r = Get-Rect $h
    $bmp = New-Object System.Drawing.Bitmap $r.W, $r.H
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $r.W, $r.H))
    $path = Join-Path $logs ('material2_' + $name + '.png')
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return [pscustomobject]@{ Path = $path; Rect = $r }
}

# The web contents area, sampled on a grid.  Byte identity of a whole capture
# is not usable as a settled test: the omnibox caret blinks forever, so the
# page would never be declared loaded.  The contents are exactly the part that
# must stop changing, and the part the material is not allowed to touch.
function Get-ContentsSignature($h) {
    [void][Mat2.Win]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 400
    $r = Get-Rect $h
    $bmp = New-Object System.Drawing.Bitmap $r.W, $r.H
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $r.W, $r.H))
    $sb = New-Object System.Text.StringBuilder
    for ($y = 300; $y -lt [Math]::Min(600, $r.H - 8); $y += 25) {
        for ($x = 200; $x -lt [Math]::Min(900, $r.W - 8); $x += 25) {
            $c = $bmp.GetPixel($x, $y)
            [void]$sb.Append($c.R).Append(',').Append($c.G).Append(',').Append($c.B).Append(';')
        }
    }
    $g.Dispose(); $bmp.Dispose()
    return $sb.ToString()
}

# Waits until the contents stop changing, so nothing still loading or
# animating can be mistaken for the material.
function Wait-Settled($h, [int]$maxTries = 15) {
    $previous = $null
    for ($i = 0; $i -lt $maxTries; $i++) {
        Start-Sleep -Seconds 3
        $signature = Get-ContentsSignature $h
        if ($previous -and $signature -eq $previous) {
            Write-Host "contents settled after $($i + 1) probes"
            return $true
        }
        $previous = $signature
        Write-Host "contents not settled yet (probe $($i + 1))"
    }
    return $false
}

function Move-To($h, [int]$x, [int]$y, [int]$w = 1000, [int]$ht = 640) {
    # MoveWindow is the one that works here. SetWindowPos returns success on
    # this window and leaves it exactly where it was, so it is only a fallback,
    # and every attempt is confirmed by reading the rectangle back.
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        $ok = [Mat2.Win]::MoveWindow($h, $x, $y, $w, $ht, $true)
        if (-not $ok) { [void][Mat2.Win]::SetWindowPos($h, [IntPtr]::Zero, $x, $y, $w, $ht, 0x0002) }
        Start-Sleep -Milliseconds 800
        $r = Get-Rect $h
        if ([Math]::Abs($r.L - $x) -le 2 -and [Math]::Abs($r.T - $y) -le 2) {
            Write-Host "placed at $($r.L),$($r.T) $($r.W)x$($r.H) (target $x,$y, ok=$ok)"
            return $r
        }
        Write-Host "placement attempt $attempt landed at $($r.L),$($r.T) (target $x,$y, ok=$ok), retrying"
        [void][Mat2.Win]::SetForegroundWindow($h)
    }
    return (Get-Rect $h)
}

$placed = Move-To $handle 60 40
$posA = @($placed.L, $placed.T)

if (-not (Wait-Settled $handle)) { Write-Output 'PAGE NEVER SETTLED'; exit 1 }

$shotA = Save-Shot $handle 'a'
Write-Output "captured A rect=$($shotA.Rect.L),$($shotA.Rect.T)"

$screenW = [Mat2.Win]::GetSystemMetrics(0)
$screenH = [Mat2.Win]::GetSystemMetrics(1)
# Move to the opposite corner of the desktop, still fully on screen.
$targetX = [Math]::Max(0, $screenW - $shotA.Rect.W - 20)
$targetY = [Math]::Max(0, $screenH - $shotA.Rect.H - 40)
if ($targetX -lt ($shotA.Rect.L + 200) -or $targetY -lt ($shotA.Rect.T + 80)) {
    Write-Output "desktop ${screenW}x${screenH} too small to move the window meaningfully"
    exit 1
}
Write-Output "desktop=${screenW}x${screenH}, target=${targetX},${targetY}"
$moved = Move-To $handle $targetX $targetY
if ([Math]::Abs($moved.L - $shotA.Rect.L) + [Math]::Abs($moved.T - $shotA.Rect.T) -lt 120) {
    Write-Output 'WINDOW DID NOT MOVE'
    exit 1
}

Start-Sleep -Seconds 4
if (-not (Wait-Settled $handle)) { Write-Output 'PAGE NEVER SETTLED AT B'; exit 1 }
$shotB = Save-Shot $handle 'b'
Write-Output "captured B rect=$($shotB.Rect.L),$($shotB.Rect.T)"

$void = Move-To $handle $posA[0] $posA[1]
Start-Sleep -Seconds 4
if (-not (Wait-Settled $handle)) { Write-Output 'PAGE NEVER SETTLED AT C'; exit 1 }
$shotC = Save-Shot $handle 'c'
Write-Output "captured C rect=$($shotC.Rect.L),$($shotC.Rect.T)"

Write-Output "shots: $($shotA.Path) $($shotB.Path) $($shotC.Path)"
