# Which requests escape the per-site allowlist?
#
# The allowlist is checked against the site a request was made from, so a site
# that is allowed can still see requests blocked when those requests were
# started by another site -- a third party frame, or a request with no
# initiator at all. This run says which URLs those were.
param(
    [string]$Url = 'https://www.foxnews.com/politics',
    [string]$Site = 'foxnews.com',
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_allow',
    [int]$Port = 9355,
    [switch]$NoAllowlist
)
$ErrorActionPreference = 'Continue'
$root = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$reader = Join-Path $root 'read_page.mjs'
$cmd = Join-Path $root 'cdp_cmd.mjs'
$detail = Join-Path $root 'cdp_allowlist_detail.mjs'

function Ask([string]$match, [string]$expr) {
    $file = Join-Path $logs 'expr.js'
    [System.IO.File]::WriteAllText($file, $expr, (New-Object System.Text.UTF8Encoding $false))
    for ($i = 0; $i - 12; $i++) {
        $out = (node $reader --port $Port --match $match --exprfile $file 2>&1) -join ' '
        if ($LASTEXITCODE -eq 0 -and $out) { return $out }
        Start-Sleep -Seconds 3
    }
    return "READ FAILED ($match)"
}

$Scan = "const all = []; const scan = (root) => {" +
    " for (const x of root.querySelectorAll('button')) all.push(x);" +
    " for (const x of root.querySelectorAll('input')) all.push(x);" +
    " for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) scan(el.shadowRoot); } };" +
    " scan(document);"

$AddSite = "(() => { $Scan" +
    " const i = all.find(x => x.tagName === 'INPUT'); if (!i) return 'NO INPUT';" +
    " i.value = '$Site'; i.dispatchEvent(new Event('input', {bubbles: true}));" +
    " const add = all.find(x => x.textContent.trim() === 'Add');" +
    " if (!add) return 'NO ADD BUTTON'; add.click(); return 'ADD CLICKED'; })()"

$AllowedSites = "(() => { $Scan" +
    " const rows = all.filter(x => x.dataset && x.dataset.index !== undefined);" +
    " return JSON.stringify(rows.map(r => r.textContent.trim())); })()"

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (Test-Path $Profile) { Remove-Item $Profile -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path (Join-Path $Profile 'Default') | Out-Null

$stderr = Join-Path $logs 'allowlist_browser.err'
$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $Port),
    '--disable-features=TabDiscarding',
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError $stderr
Write-Host "launched pid=$($proc.Id)"

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

for ($i = 0; $i - 20; $i++) {
    [void](node $cmd --port $Port --match 'chrome://newtab/' --method Page.navigate --url 'chrome://paani/' 2>&1)
    Start-Sleep -Seconds 2
    $urls = (Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/list") -TimeoutSec 5 |
        ForEach-Object { $_.url })
    if ($urls -match '^chrome://paani/') { break }
}
Write-Host ("open targets                  : " + ($urls -join ' | '))

if ($NoAllowlist) {
    Write-Host 'allowlist                     : (not set, the engine stays on)'
} else {
    Write-Host ("allowlist add                 : " + (Ask 'chrome://paani/' $AddSite))
    Start-Sleep -Seconds 3
    Write-Host ("allowlist now                 : " + (Ask 'chrome://paani/' $AllowedSites))
}

# Paani's own counter is the number of requests its engine answered, which
# includes the ones that were answered with a stub instead of being failed.
# The renderer only sees the failed ones, so both numbers are needed.
Write-Host ("reset counter                : " + (Ask 'chrome://paani/' $ResetCounter))
$before = (Ask 'chrome://paani/' "__q('.counter')").Trim()
Write-Host "counter before the page load  : $before"

Write-Host '--- requests made by the page ---'
node $detail $Port $Url 40 2>&1 | Tee-Object -FilePath (Join-Path $logs 'allowlist_detail.txt')

$after = (Ask 'chrome://paani/' "__q('.counter')").Trim()
Write-Host "counter after the page load   : $after"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host 'DONE'
