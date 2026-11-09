# Ties the number on the toolbar button to Paani's own counter.
#
# The button is found in the accessibility tree, and the site is then
# allowlisted through Paani's own WebUI.  If the number on the button is
# Paani's blocked count for the tab, it has to disappear when the site is
# allowlisted and come back when the allowlist entry is removed.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe'
$profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_a11y2'
$port = 9355
$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$logs = Join-Path $verify 'logs'

Get-Process paani -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like 'E:\eric\PaaniBrowserChromiumFork\*' } |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
if (Test-Path $profile) { Remove-Item $profile -Recurse -Force }

$proc = Start-Process -FilePath $exe -ArgumentList @(
    ('--user-data-dir=' + $profile),
    '--no-first-run', '--no-default-browser-check',
    ('--remote-debugging-port=' + $port),
    '--force-renderer-accessibility',
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError (Join-Path $logs 'a11y2_browser.err')

for ($i = 0; $i - 40; $i++) {
    try { Invoke-RestMethod -Uri ("http://127.0.0.1:$port/json/version") -TimeoutSec 3 | Out-Null; break }
    catch { Start-Sleep -Seconds 1 }
}
Write-Host 'browser up'

Invoke-RestMethod -Method Put -Uri ("http://127.0.0.1:$port/json/new?" +
    [uri]::EscapeDataString('https://www.foxnews.com/politics')) | Out-Null
Start-Sleep -Seconds 30

# The buttons of the toolbar, with the position they sit at, so the same
# button can be followed across the three readings.
function ToolbarButtons($handle) {
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Button)
    $buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    $out = @()
    foreach ($b in $buttons) {
        $rect = $b.Current.BoundingRectangle
        if ([int]$rect.Y -gt 120) { continue }   # the page, not the toolbar
        $out += [pscustomobject]@{
            Name = $b.Current.Name
            X = [int]$rect.X
            W = [int]$rect.Width
        }
    }
    return $out
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

Write-Host '--- before the allowlist ---'
$before = ToolbarButtons $handle
foreach ($b in $before) { Write-Host ("  x={0} w={1} name='{2}'" -f $b.X, $b.W, $b.Name) }

# Allowlist the site through Paani's own WebUI.
[void](node (Join-Path $verify 'cdp_cmd.mjs') --port $port --match 'chrome://newtab/' --method Page.navigate --url 'chrome://paani/' 2>&1)
Start-Sleep -Seconds 4
$expr = Join-Path $logs 'a11y_allow.js'
[System.IO.File]::WriteAllText($expr, @'
(() => { const roots = [document]; const work = [document];
  while (work.length) { for (const el of work.pop().querySelectorAll('*')) {
    if (el.shadowRoot) { roots.push(el.shadowRoot); work.push(el.shadowRoot); } } }
  const all = []; for (const r of roots) for (const b of r.querySelectorAll('button,input')) all.push(b);
  const i = all.find(x => x.tagName === 'INPUT');
  if (!i) return 'NO INPUT';
  i.value = 'foxnews.com'; i.dispatchEvent(new Event('input', {bubbles: true}));
  const add = all.find(x => x.textContent.trim() === 'Add');
  if (!add) return 'NO ADD BUTTON';
  add.click(); return 'ADD CLICKED'; })()
'@, (New-Object System.Text.UTF8Encoding $false))
$added = (node (Join-Path $verify 'read_page.mjs') --port $port --match 'chrome://paani/' --exprfile $expr 2>&1) -join ' '
Write-Host "allowlist: $added"
Start-Sleep -Seconds 4

# Reload the page so the tab starts over with the allowlist in force.
[void](node (Join-Path $verify 'cdp_cmd.mjs') --port $port --match 'https://www.foxnews.com' --method Page.reload --url '' 2>&1)
Start-Sleep -Seconds 25

Write-Host '--- after the allowlist ---'
$after = ToolbarButtons $handle
foreach ($b in $after) { Write-Host ("  x={0} w={1} name='{2}'" -f $b.X, $b.W, $b.Name) }

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host 'DONE'
