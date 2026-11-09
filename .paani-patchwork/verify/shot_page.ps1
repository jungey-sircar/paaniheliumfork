# Captures one page of the freshly built browser, at a known place on the
# desktop, so the surfaces can be measured from pixels instead of assumed.
param(
    [string]$Url = 'chrome://new-tab-page',
    [string]$Name = 'ntp',
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_pages',
    [int]$Port = 9348,
    [int]$X = 200,
    [int]$Y = 80
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Shot -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int cx, int cy, bool repaint);
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
public struct R { public int L,T,Rr,B; }
'@

$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $Port),
    '--window-size=1000,640', ('--window-position={0},{1}' -f $X, $Y),
    $Url
) -PassThru

$h = [IntPtr]::Zero
for ($i = 0; $i -lt 25; $i++) {
    Start-Sleep -Seconds 2
    $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if ($p -and $p.MainWindowHandle -ne 0) { $h = $p.MainWindowHandle; break }
}
if ($h -eq [IntPtr]::Zero) { Write-Output 'NO WINDOW'; exit 1 }

function Rect($hwnd) {
    $r = New-Object Shot.Win+R
    [void][Shot.Win]::GetWindowRect($hwnd, [ref]$r)
    return [pscustomobject]@{L=$r.L; T=$r.T; W=($r.Rr-$r.L); H=($r.B-$r.T)}
}

# Two captures until they agree, so nothing still loading is measured.
$prev = $null
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 3
    [void][Shot.Win]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 400
    $r = Rect $h
    $bmp = New-Object System.Drawing.Bitmap $r.W, $r.H
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $r.W, $r.H))
    $tmp = Join-Path $logs ('shot_' + $Name + '.png')
    $bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    $hash = (Get-FileHash -Algorithm MD5 -Path $tmp).Hash
    if ($prev -and $hash -eq $prev) { Write-Output "settled rect=$($r.L),$($r.T) $($r.W)x$($r.H) -> $tmp"; exit 0 }
    $prev = $hash
    Write-Output "not settled (probe $($i+1))"
}
Write-Output "never settled, last capture is at $tmp"
