# Does the toolbar shield tell the truth about the built in blocker?
#
# Paani's interceptor is the first factory in the chain, so a request its own
# counter records was matched by Paani's own engine -- the number cannot be
# borrowed from uBlock. The numbers come from the page itself instead of from
# pixels; the screenshots only show that the badge on the toolbar agrees.
#
# The shield shows the count of the tab in front of the user, so the tab under
# test is made the active one before every capture.
param(
    [string]$Url = 'https://www.foxnews.com/politics',
    [string]$Site = 'foxnews.com',
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_shield',
    [int]$Port = 9333
)
$ErrorActionPreference = 'Continue'
$root = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$logs = Join-Path $root 'logs'
$reader = Join-Path $root 'read_page.mjs'

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Shield -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
public struct R { public int L,T,Rr,B; }
'@

function Ask([string]$match, [string]$expr) {
    for ($i = 0; $i - 12; $i++) {
        $out = (node $reader --port $Port --match $match --expr $expr 2>&1) -join ' '
        if ($LASTEXITCODE -eq 0 -and $out) { return $out }
        Start-Sleep -Seconds 3
    }
    return "READ FAILED ($match)"
}

# Puts the tab under test in front, because the badge counts the active tab.
function Activate([string]$match) {
    $targets = Invoke-RestMethod "http://127.0.0.1:$Port/json/list"
    $t = $targets | Where-Object { $_.url -like "$match*" } | Select-Object -First 1
    if (-not $t) { Write-Host "no tab matching $match"; return $false }
    Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/json/activate/$($t.id)" | Out-Null
    Start-Sleep -Milliseconds 800
    return $true
}

function Capture([string]$name) {
    $p = Get-Process paani -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
        Select-Object -First 1
    if (-not $p) { Write-Host 'no browser window'; return }
    [void][Shield.Win]::SetForegroundWindow($p.MainWindowHandle)
    Start-Sleep -Milliseconds 600
    $r = New-Object Shield.Win+R
    [void][Shield.Win]::GetWindowRect($p.MainWindowHandle, [ref]$r)
    $w = $r.Rr - $r.L
    $h = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save((Join-Path $logs ("shield_{0}.png" -f $name)), [System.Drawing.Imaging.ImageFormat]::Png)
    # The toolbar strip on its own, so the badge can be read without hunting
    # for it in the full window.
    $strip = New-Object System.Drawing.Bitmap $w, 140
    $gs = [System.Drawing.Graphics]::FromImage($strip)
    $gs.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $w, 140), (New-Object System.Drawing.Rectangle 0, 0, $w, 140), [System.Drawing.GraphicsUnit]::Pixel)
    $strip.Save((Join-Path $logs ("shield_{0}_toolbar.png" -f $name)), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose(); $gs.Dispose(); $strip.Dispose()
    Write-Host ("captured shield_{0}.png at {1},{2} {3}x{4}" -f $name, $r.L, $r.T, $w, $h)
}

$ResetCounter = "(() => { const b = Array.from(document.querySelectorAll('button'));" +
    " const all = []; const scan = (root) => { for (const el of root.querySelectorAll('*')) {" +
    " if (el.shadowRoot) scan(el.shadowRoot); } for (const x of root.querySelectorAll('button')) all.push(x); };" +
    " scan(document); const hit = all.find(x => x.textContent.trim() === 'Reset counter');" +
    " if (!hit) return 'NO RESET BUTTON'; hit.click(); return 'RESET CLICKED'; })()"

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# uBlock's component extension stays out of this run so nothing but Paani's own
# engine can be the reason an ad request is gone.
$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    '--disable-component-extensions-with-background-pages',
    ('--remote-debugging-port=' + $Port),
    '--window-position=60,40', '--window-size=1280,820',
    $Url, 'chrome://paani'
) -PassThru
Write-Host "launched pid=$($proc.Id)"

Start-Sleep -Seconds 30

$engine = Ask 'chrome://paani' "__q('.engine-status')"
Write-Host "engine status               : $engine"

# --- while the site is blocked ---
Write-Host ("reset counter               : " + (Ask 'chrome://paani' $ResetCounter))
[void](node $reader --port $Port --match 'https' "location.reload(); 'reloading'")
Start-Sleep -Seconds 30
$blocked = Ask 'chrome://paani' "__q('.counter')"
Write-Host "counter while blocking      : $blocked"
[void](Activate 'https://')
Capture 'blocking'

# --- allowlist the site and load it again ---
$added = Ask 'chrome://paani' ("(() => { const all = [];" +
    " const scan = (root) => { for (const x of root.querySelectorAll('input')) all.push(x);" +
    " for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) scan(el.shadowRoot); } };" +
    " scan(document); const i = all[0]; if (!i) return 'NO INPUT';" +
    " i.value = '$Site'; i.dispatchEvent(new Event('input', {bubbles: true}));" +
    " const btns = []; const scan2 = (root) => { for (const x of root.querySelectorAll('button')) btns.push(x);" +
    " for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) scan2(el.shadowRoot); } };" +
    " scan2(document); const add = btns.find(x => x.textContent.trim() === 'Add');" +
    " if (!add) return 'NO ADD BUTTON'; add.click(); return 'ADD CLICKED'; })()")
Write-Host "allowlist                   : $added"
Start-Sleep -Seconds 3
Write-Host ("reset counter               : " + (Ask 'chrome://paani' $ResetCounter))
[void](node $reader --port $Port --match 'https' "location.reload(); 'reloading'")
Start-Sleep -Seconds 30
$allowed = Ask 'chrome://paani' "__q('.counter')"
Write-Host "counter while allowed       : $allowed"
[void](Activate 'https://')
Capture 'allowed'

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host "blocked=$blocked allowed=$allowed"
Write-Host 'DONE'
