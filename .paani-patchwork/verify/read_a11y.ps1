# Reads the Paani shield button out of the browser window.
#
# The badge is a views widget, not a native control, so it cannot be read with
# a window handle.  Chromium publishes its widgets through the accessibility
# tree, so the button is found there by its accessible name, and the number it
# shows is read from the same tree.
#
# The screenshot cannot be used for this: the browser is not the window on the
# screen, and PrintWindow does not paint the right hand side of the toolbar.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -Namespace Shot -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
public struct R { public int L,T,Rr,B; }
'@

$exe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe'
$profile = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\profile_a11y'
$port = 9354
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
    # Without this the accessibility tree is only built when a screen reader
    # asks for it, and there is no screen reader here.
    '--force-renderer-accessibility',
    '--window-position=60,40', '--window-size=1280,820'
) -PassThru -RedirectStandardError (Join-Path $logs 'a11y_browser.err')

for ($i = 0; $i - 40; $i++) {
    try { Invoke-RestMethod -Uri ("http://127.0.0.1:$port/json/version") -TimeoutSec 3 | Out-Null; break }
    catch { Start-Sleep -Seconds 1 }
}
Write-Host 'browser up'

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

$root = [System.Windows.Automation.AutomationElement]::FromHandle($handle)
$condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button)
$buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
Write-Host "buttons found: $($buttons.Count)"
foreach ($b in $buttons) {
    $name = $b.Current.Name
    $help = $b.Current.HelpText
    $rect = $b.Current.BoundingRectangle
    Write-Host ("button: name='{0}' help='{1}' at {2},{3} {4}x{5}" -f `
        $name, $help, [int]$rect.X, [int]$rect.Y, [int]$rect.Width, [int]$rect.Height)
}

# The shield button carries the number as its text, which the tree reports as
# the value of the element.
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants,
    [System.Windows.Automation.Condition]::TrueCondition)
foreach ($e in $all) {
    $name = $e.Current.Name
    if ($name -like '*Paani*') {
        $value = ''
        try { $value = $e.GetCurrentPattern(
            [System.Windows.Automation.ValuePattern]::Pattern).Current.Value } catch {}
        Write-Host ("paani element: name='{0}' type={1} value='{2}' help='{3}'" -f `
            $name, $e.Current.ControlType.ProgrammaticName, $value, $e.Current.HelpText)
    }
}

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Write-Host 'DONE'
