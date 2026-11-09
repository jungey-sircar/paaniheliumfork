# Does the toolbar shield tell the truth about the built in blocker?
#
# Paani's interceptor is the first factory in the chain, so a request its own
# counter records was matched by Paani's own engine -- the number cannot be
# borrowed from uBlock. The numbers come from the page and from the WebUI
# instead of from pixels; the screenshots only show that the badge on the
# toolbar agrees with them.
#
# Three phases, in this order:
#
#   phase 0  the blocker is switched off, the page is loaded, the counter has
#             to stay at zero. Helium's own uBlock Origin component extension
#             is still installed and still blocks ads in this phase, so a
#             non zero counter here would mean the counter is counting
#             somebody else's work.
#   phase 1  the blocker is switched on, the same page is loaded, and the
#             counter has to be greater than zero: Paani's own engine matched
#             and blocked the requests itself.
#   phase 2  the site is allowlisted, the page is loaded again, and the
#             counter has to stay at zero: Paani's own allowlist switched its
#             own engine off for that site.
#
# The badge counts the tab in front of the user, and a tab keeps its count for
# as long as it lives, so every phase opens a fresh tab. Reloading the old one
# would carry the number of the previous phase into the next one.
param(
    [string]$Url = 'https://www.foxnews.com/politics',
    [string]$Site = 'foxnews.com',
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_shield2',
    [int]$Port = 9345
)
$ErrorActionPreference = 'Continue'
$root = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$reader = Join-Path $root 'read_page.mjs'
$cmd = Join-Path $root 'cdp_cmd.mjs'

# Helium ships uBlock Origin as a component extension. Its component id, and
# the switches that would disable it, do not touch it: uBlock is added by
# AddDefaultComponentExtensions, and the command line switches only gate
# AddDefaultComponentExtensionsWithBackgroundPages and the extension system
# at large. Its state also lives in the protected "Secure Preferences" file,
# so a profile cannot switch it off either.
#
# It does not matter for the numbers: the interceptor that counts is Paani's
# own, and phase 0 shows that the counter stays at zero while Paani's engine
# is off, even though uBlock is still blocking.
$UBlockId = 'blockjmkbacgjkknlgpkjjiijinjdanf'

Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Shield -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
public struct R { public int L,T,Rr,B; }
'@

function Ask([string]$match, [string]$expr) {
    # The expression is written to a file and handed to the reader as a path:
    # a long piece of JavaScript does not survive a Windows command line.
    $file = Join-Path $logs 'expr.js'
    [System.IO.File]::WriteAllText($file, $expr, (New-Object System.Text.UTF8Encoding $false))
    for ($i = 0; $i - 12; $i++) {
        $out = (node $reader --port $Port --match $match --exprfile $file 2>&1) -join ' '
        if ($LASTEXITCODE -eq 0 -and $out) { return $out }
        Start-Sleep -Seconds 3
    }
    return "READ FAILED ($match)"
}

function TargetUrls() {
    try {
        return (Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/list") -TimeoutSec 5 |
            ForEach-Object { $_.url })
    } catch {
        return @()
    }
}

# The page only reads the state when it is connected, so a number that grew
# while it was open is only picked up after the WebUI is opened again. A
# location.reload() is not enough: it keeps the element tree and the number
# that was rendered into it, so the page is navigated to itself instead, which
# builds a fresh page that asks the browser for the current state.
#
# Chromium's tab discarder can take the WebUI tab away while it is in the
# background, and a discarded tab comes back as chrome://newtab/. So the
# WebUI is not looked for by name only: any chrome:// tab can be turned into
# the WebUI, and a fresh tab is opened when there is none left.
function ReloadWebUI() {
    $urls = TargetUrls
    if ($urls -match '^chrome://paani/') {
        [void](node $cmd --port $Port --match 'chrome://paani/' --method Page.navigate --url 'chrome://paani/' 2>&1)
    } elseif ($urls -match '^chrome://') {
        Write-Host '  (the WebUI tab was discarded, another chrome:// tab is used)'
        [void](node $cmd --port $Port --match '^chrome://' --regex true --method Page.navigate --url 'chrome://paani/' 2>&1)
    } else {
        Write-Host '  (no chrome:// tab is left, a new one is opened)'
        try {
            Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:$Port/json/new?" +
                [uri]::EscapeDataString('about:blank')) | Out-Null
            Start-Sleep -Seconds 2
        } catch { }
        [void](node $cmd --port $Port --match 'about:blank' --method Page.navigate --url 'chrome://paani/' 2>&1)
    }
    Start-Sleep -Seconds 4
    # If it still did not come up, take any tab that is there and drive it to
    # the WebUI again, whatever it is showing.
    if (-not (TargetUrls -match '^chrome://paani/')) {
        [void](node $cmd --port $Port --match '.' --regex true --method Page.navigate --url 'chrome://paani/' 2>&1)
        Start-Sleep -Seconds 4
    }
}

function Counter() {
    ReloadWebUI
    return (Ask 'chrome://paani/' "__q('.counter')").Trim()
}

# A zero counter is only evidence when the page actually loaded. This says
# what the browser title of the test page is.
function PageTitle() {
    return (Ask $Url 'document.title').Trim()
}

# Opens a new tab, so the tab's own counter starts at zero.
function NewTab([string]$url) {
    $r = Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:$Port/json/new?" + [uri]::EscapeDataString($url))
    Start-Sleep -Seconds 2
    return $r.id
}

# The counter behind chrome://paani is a profile counter: it counts every
# request the profile blocks, whichever tab made it. A page that keeps
# loading ads after it was read would therefore push its requests into the
# next phase's number. The tabs of the previous phase are closed before a new
# one is opened, so each phase counts only its own page.
function CloseOtherTabs() {
    $targets = Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/list") -TimeoutSec 5
    foreach ($t in $targets) {
        if ($t.type -ne 'page') { continue }
        if ($t.url -like 'chrome://paani*') { continue }
        try {
            Invoke-WebRequest -UseBasicParsing ("http://127.0.0.1:$Port/json/close/" + $t.id) | Out-Null
        } catch { }
    }
    Start-Sleep -Seconds 3
}

# A closed page can still have requests in flight, and those would land in
# the counter of the next phase. The counter is therefore reset twice with a
# pause in between: the first reset throws away what the old page left, the
# second throws away what arrived while the first reset was being applied.
function SettleAndReset() {
    CloseOtherTabs
    Start-Sleep -Seconds 6
    [void](Ask 'chrome://paani/' $ResetCounter)
    Start-Sleep -Seconds 4
    [void](Ask 'chrome://paani/' $ResetCounter)
    Start-Sleep -Seconds 2
}

# What the counter says before the page of the phase is even opened. A number
# that is not zero here did not come from the page the phase is about to load.
function CounterNow() {
    return (Ask 'chrome://paani/' "__q('.counter')").Trim()
}

function Activate([string]$id) {
    Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/json/activate/$id" | Out-Null
    Start-Sleep -Milliseconds 1200
}

function Capture([string]$name) {
    # Only the browser process owns a window; the renderers and the utility
    # processes have none, and a window rectangle of zero cannot be captured.
    $p = Get-Process paani -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' -and $_.MainWindowHandle -ne 0 } |
        Sort-Object { $_.MainWindowTitle.Length } -Descending |
        Select-Object -First 1
    if (-not $p) { Write-Host 'no browser window'; return }
    [void][Shield.Win]::SetForegroundWindow($p.MainWindowHandle)
    Start-Sleep -Milliseconds 900
    $r = New-Object Shield.Win+R
    [void][Shield.Win]::GetWindowRect($p.MainWindowHandle, [ref]$r)
    $w = $r.Rr - $r.L
    $h = $r.B - $r.T
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $h))
    $bmp.Save((Join-Path $logs ("shield2_{0}.png" -f $name)), [System.Drawing.Imaging.ImageFormat]::Png)
    # The toolbar strip on its own, so the badge can be read without hunting
    # for it in the full window.
    $strip = New-Object System.Drawing.Bitmap $w, 150
    $gs = [System.Drawing.Graphics]::FromImage($strip)
    $gs.DrawImage($bmp, (New-Object System.Drawing.Rectangle 0, 0, $w, 150), (New-Object System.Drawing.Rectangle 0, 0, $w, 150), [System.Drawing.GraphicsUnit]::Pixel)
    $strip.Save((Join-Path $logs ("shield2_{0}_toolbar.png" -f $name)), [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose(); $gs.Dispose(); $strip.Dispose()
    Write-Host ("captured shield2_{0}.png {1}x{2}" -f $name, $w, $h)
}

# Every element of the WebUI lives in a shadow root, so the helpers walk them.
$Scan = "const all = []; const scan = (root) => {" +
    " for (const x of root.querySelectorAll('button')) all.push(x);" +
    " for (const x of root.querySelectorAll('input')) all.push(x);" +
    " for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) scan(el.shadowRoot); } };" +
    " scan(document);"

$ResetCounter = "(() => { $Scan" +
    " const hit = all.find(x => x.textContent.trim() === 'Reset counter');" +
    " if (!hit) return 'NO RESET BUTTON'; hit.click(); return 'RESET CLICKED'; })()"

$AddSite = "(() => { $Scan" +
    " const i = all.find(x => x.tagName === 'INPUT'); if (!i) return 'NO INPUT';" +
    " i.value = '$Site'; i.dispatchEvent(new Event('input', {bubbles: true}));" +
    " const add = all.find(x => x.textContent.trim() === 'Add');" +
    " if (!add) return 'NO ADD BUTTON'; add.click(); return 'ADD CLICKED'; })()"

$RemoveSite = "(() => { $Scan" +
    " const rm = all.find(x => x.textContent.trim() === 'Remove');" +
    " if (!rm) return 'NO REMOVE BUTTON'; rm.click(); return 'REMOVE CLICKED'; })()"

# Reads the allowlist back, so a run can say whether the entry is really there
# instead of trusting that the button was clicked.
$AllowedSites = "(() => { $Scan" +
    " const rows = all.filter(x => x.dataset && x.dataset.index !== undefined);" +
    " return JSON.stringify(rows.map(r => r.textContent.trim())); })()"

$ToggleState = "(() => { $Scan" +
    " const t = all.find(x => x.classList && x.classList.contains('toggle'));" +
    " return t ? t.getAttribute('aria-checked') : 'NO TOGGLE'; })()"

$ToggleClick = "(() => { $Scan" +
    " const t = all.find(x => x.classList && x.classList.contains('toggle'));" +
    " if (!t) return 'NO TOGGLE'; t.click(); return 'TOGGLE CLICKED'; })()"

# Brings the blocker into the wanted state and says what it did.
function SetBlocking([bool]$want) {
    for ($i = 0; $i - 8; $i++) {
        $state = (Ask 'chrome://paani/' $ToggleState).Trim()
        if ($state -eq 'true' -and $want) { return "already on ($state)" }
        if ($state -eq 'false' -and -not $want) { return "already off ($state)" }
        [void](Ask 'chrome://paani/' $ToggleClick)
        Start-Sleep -Seconds 2
    }
    return "COULD NOT SET BLOCKING TO $want"
}

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# A fresh profile.
if (Test-Path $Profile) { Remove-Item $Profile -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path (Join-Path $Profile 'Default') | Out-Null

$stderr = Join-Path $logs 'shield2_browser.err'
$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $Port),
    # The tab discarder takes a background WebUI tab away and brings it back
    # as chrome://newtab/, which is what broke an earlier run.
    '--disable-features=TabDiscarding',
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError $stderr
Write-Host "launched pid=$($proc.Id)"

# Wait for the browser to answer, and say so plainly if it died instead of
# leaving every later read to fail with a connection error.
$up = $false
for ($i = 0; $i - 40; $i++) {
    if ($proc.HasExited) { break }
    try {
        Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/version") -TimeoutSec 3 | Out-Null
        $up = $true
        break
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $up) {
    Write-Host "BROWSER DID NOT COME UP. exit=$($proc.ExitCode)"
    if (Test-Path $stderr) { Get-Content $stderr -Tail 30 }
    exit 1
}
Write-Host 'browser is up'

# Chromium ignores a chrome:// URL that is handed to it on the command line and
# a WebUI page cannot navigate itself to another chrome:// URL either. The
# browser's own navigation call can, so the WebUI is opened that way. The URL
# is passed on its own instead of as a JSON blob, which PowerShell would
# mangle on the native command line.
for ($i = 0; $i - 20; $i++) {
    $out = (node $cmd --port $Port --match 'chrome://newtab/' --method Page.navigate --url 'chrome://paani/' 2>&1) -join ' '
    Write-Host ("navigate attempt {0}: {1} (exit {2})" -f $i, $out, $LASTEXITCODE)
    Start-Sleep -Seconds 2
    if ((TargetUrls) -match '^chrome://paani/') { break }
}
$urls = TargetUrls
Write-Host ("open targets                  : " + ($urls -join ' | '))
if (-not ($urls -match '^chrome://paani/')) {
    Write-Host 'THE PAANI WEBUI DID NOT OPEN'
    if (Test-Path $stderr) { Get-Content $stderr -Tail 30 }
    exit 1
}
if ($urls -match 'chrome-extension://') {
    Write-Host ("note: extensions are running   : " + (($urls | Where-Object { $_ -match 'chrome-extension://' }) -join ' | '))
}
Start-Sleep -Seconds 3

$engine = Ask 'chrome://paani/' "__q('.engine-status')"
Write-Host "engine status                : $engine"
# Nothing is blocked until the filter lists are in, so wait for the engine
# instead of blaming an empty counter on an engine that is still loading.
for ($i = 0; $i - 20; $i++) {
    if ($engine -like '*Filter engine ready*') { break }
    Start-Sleep -Seconds 6
    $engine = Ask 'chrome://paani/' "__q('.engine-status')"
    Write-Host "engine status                : $engine"
}
Write-Host ("reset counter                : " + (Ask 'chrome://paani/' $ResetCounter))

# --- phase 0: Paani's own engine is off, so its counter has to stay at zero ---
Write-Host ("blocker off                  : " + (SetBlocking $false))
SettleAndReset
Write-Host "phase0 counter before the load : $(CounterNow)"
$tab0 = NewTab $Url
Start-Sleep -Seconds 35
$off = Counter
Write-Host "phase0 counter with the engine off: $off"
Write-Host "phase0 page title              : $(PageTitle)"
Activate $tab0
Capture 'off'

# --- phase 1: the engine is on and blocks ---
Write-Host ("blocker on                   : " + (SetBlocking $true))
SettleAndReset
Write-Host "phase1 counter before the load : $(CounterNow)"
$tab1 = NewTab $Url
Start-Sleep -Seconds 35
$blocked = Counter
Write-Host "phase1 profile counter       : $blocked"
Write-Host "phase1 page title            : $(PageTitle)"
Activate $tab1
Capture 'blocking'

# --- phase 2: the same site is allowlisted ---
Write-Host ("allowlist                    : " + (Ask 'chrome://paani/' $AddSite))
Start-Sleep -Seconds 3
Write-Host ("allowlist now                : " + (Ask 'chrome://paani/' $AllowedSites))
SettleAndReset
Write-Host "phase2 counter before the load : $(CounterNow)"
$tab2 = NewTab $Url
Start-Sleep -Seconds 35
$allowed = Counter
Write-Host "phase2 profile counter       : $allowed"
Start-Sleep -Seconds 20
$allowed_later = CounterNow
Write-Host "phase2 profile counter later : $allowed_later"
Write-Host "phase2 page title            : $(PageTitle)"
Activate $tab2
Capture 'allowed'

# --- phase 3: the site is taken off the allowlist again ---
# The control for phase 2: if the allowlist is what held the counter down,
# taking it off has to let the blocking start again.
Write-Host ("allowlist removed            : " + (Ask 'chrome://paani/' $RemoveSite))
Start-Sleep -Seconds 3
Write-Host ("allowlist now                : " + (Ask 'chrome://paani/' $AllowedSites))
SettleAndReset
$tab3 = NewTab $Url
Start-Sleep -Seconds 35
$removed = Counter
Write-Host "phase3 profile counter       : $removed"
Write-Host "phase3 page title            : $(PageTitle)"
Activate $tab3
Capture 'removed'

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host "phase0_off=$off phase1_blocked=$blocked phase2_allowed=$allowed phase3_removed=$removed"
Write-Host 'DONE'
