# Is Helium's uBlock Origin component extension really gone?
#
# The patch that removes it only changes one function in
# chrome/browser/extensions/component_loader.cc, so the proof has to come from
# the running browser: the component extension must not be installed, and the
# Chrome Web Store component extension must still be there.
#
# chrome://extensions-internals prints the installed extensions as JSON, which
# is read straight out of the page.

param(
    [string]$Exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$Profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_noub',
    [int]$Port = 9347
)
$ErrorActionPreference = 'Continue'
$root = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$reader = Join-Path $root 'read_page.mjs'
$cmd = Join-Path $root 'cdp_cmd.mjs'

$UBlockId = 'blockjmkbacgjkknlgpkjjiijinjdanf'

function TargetUrls() {
    try {
        return (Invoke-RestMethod -Uri ("http://127.0.0.1:$Port/json/list") -TimeoutSec 5 |
            ForEach-Object { $_.url })
    } catch {
        return @()
    }
}

function Ask([string]$match, [string]$expr) {
    $file = Join-Path $logs 'expr_noub.js'
    [System.IO.File]::WriteAllText($file, $expr, (New-Object System.Text.UTF8Encoding $false))
    for ($i = 0; $i - 12; $i++) {
        $out = (node $reader --port $Port --match $match --exprfile $file 2>&1) -join "`n"
        if ($LASTEXITCODE -eq 0 -and $out) { return $out }
        Start-Sleep -Seconds 3
    }
    return "READ FAILED ($match)"
}

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' -or $_.Path -like "$env:LOCALAPPDATA\Paani\*" } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

if (Test-Path $Profile) { Remove-Item $Profile -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Force -Path (Join-Path $Profile 'Default') | Out-Null

$stderr = Join-Path $logs 'noub_browser.err'
$proc = Start-Process -FilePath $Exe -ArgumentList @(
    ('--user-data-dir=' + $Profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $Port),
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

# A WebUI page cannot navigate itself to another chrome:// URL, so the browser's
# own navigation call does it.
for ($i = 0; $i - 20; $i++) {
    [void](node $cmd --port $Port --match 'chrome://newtab/' --method Page.navigate --url 'chrome://extensions-internals' 2>&1)
    Start-Sleep -Seconds 2
    if ((TargetUrls) -match '^chrome://extensions-internals') { break }
}
$urls = TargetUrls
Write-Host ("open targets                  : " + ($urls -join ' | '))
if (-not ($urls -match '^chrome://extensions-internals')) {
    Write-Host 'THE EXTENSIONS INTERNALS PAGE DID NOT OPEN'
    if (Test-Path $stderr) { Get-Content $stderr -Tail 30 }
    exit 1
}
Start-Sleep -Seconds 4

# The page prints the installed extensions as JSON. The names and the ids are
# what is needed, not the whole blob.
$Names = "(() => { const t = document.body.innerText; const ids = [...t.matchAll(/""id"":\s*""([a-p]{32})""/g)].map(m => m[1]); return JSON.stringify({ids: ids, hasUBlock: /ublock/i.test(t), hasWebStore: /web.?store/i.test(t)}); })()"
$report = Ask 'chrome://extensions-internals' $Names
Write-Host "installed extensions          : $report"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue

$ok = $true
if ($report -match '"hasUBlock":true') {
    Write-Host 'RESULT: uBlock is still installed'
    $ok = $false
}
if ($report -match $UBlockId) {
    Write-Host "RESULT: the uBlock component id $UBlockId is still present"
    $ok = $false
}
if ($report -match '"hasWebStore":false') {
    Write-Host 'RESULT: the Chrome Web Store component is missing'
    $ok = $false
}
if ($ok) {
    Write-Host 'RESULT: no uBlock extension, Chrome Web Store component present'
    Write-Host 'DONE'
} else {
    exit 1
}
