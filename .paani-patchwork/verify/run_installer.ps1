# Runs the Paani installer and answers its wizard.
#
# The installer is a GUI wizard, so it has to be clicked through.  Every step
# prints what the window offers before it clicks, so the log says what was
# done rather than only that something was done.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$installer = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\mini_installer.exe'
$logs = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'

Get-Process mini_installer -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

$proc = Start-Process -FilePath $installer -PassThru
Write-Host "installer pid: $($proc.Id)"

function WindowsOfInstaller() {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $condition = New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $proc.Id)
    return $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
}

function Describe($w) {
    $parts = @()
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        $name = $child.Current.Name
        if ($name) { $parts += ("[{0}] {1}" -f $child.Current.ControlType.ProgrammaticName.Replace('ControlType.', ''), $name) }
    }
    return ($parts -join ' | ')
}

function Click($w, [string[]]$names) {
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        $name = $child.Current.Name
        foreach ($wanted in $names) {
            if ($name -replace '&', '' -eq $wanted) {
                $pattern = $null
                if ($child.TryGetCurrentPattern(
                        [System.Windows.Automation.InvokePattern]::Pattern,
                        [ref]$pattern)) {
                    $pattern.Invoke()
                    Write-Host "clicked '$name'"
                    return $true
                }
            }
        }
    }
    return $false
}

# The wizard has a welcome page, a license page, an install type page, the
# install itself and a finish page.  The button names are the same on every
# page, so each step is driven by what the page shows.
for ($step = 1; $step -le 12; $step++) {
    $clicked = $false
    for ($wait = 0; $wait -lt 30 -and -not $clicked; $wait++) {
        $windows = WindowsOfInstaller
        foreach ($w in $windows) {
            Write-Host ("page: '{0}' -> {1}" -f $w.Current.Name, (Describe $w))
            $clicked = Click $w @('Next >', 'Install', 'Finish')
            if ($clicked) { break }
        }
        if (-not $clicked) { Start-Sleep -Seconds 2 }
    }
    if (-not $clicked) {
        Write-Host 'no button to click on this page'
        Start-Sleep -Seconds 3
    } else {
        Start-Sleep -Seconds 3
    }
    if ($proc.HasExited) { break }
}

Start-Sleep -Seconds 10
Write-Host ("installer exited: {0} (code {1})" -f $proc.HasExited, $(if ($proc.HasExited) { $proc.ExitCode } else { 'still running' }))

# The finish page can launch the browser.  It is left to the user, so the
# checkbox is cleared before the window is closed.
$windows = WindowsOfInstaller
foreach ($w in $windows) {
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($child.Current.Name -like '*Launch Paani*') {
            $toggle = $null
            if ($child.TryGetCurrentPattern(
                    [System.Windows.Automation.TogglePattern]::Pattern, [ref]$toggle)) {
                $state = $toggle.Current.ToggleState
                if ($state -eq [System.Windows.Automation.ToggleState]::On) {
                    $toggle.Toggle()
                    Write-Host 'cleared the launch checkbox'
                }
            }
        }
    }
}

if (-not $proc.HasExited) {
    $windows = WindowsOfInstaller
    foreach ($w in $windows) { [void](Click $w @('Finish')) }
    Start-Sleep -Seconds 5
}
Write-Host 'DONE'
