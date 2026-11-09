# Answers the Paani installer wizard that is already on the screen.
#
# The wizard runs in its own process, so the window is found by its title
# instead of by the id of the launcher.

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

function SetupWindows() {
    $root = [System.Windows.Automation.AutomationElement]::RootElement
    $all = $root.FindAll([System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.Condition]::TrueCondition)
    $found = @()
    foreach ($w in $all) {
        if ($w.Current.Name -like 'Paani Setup*') { $found += $w }
    }
    return $found
}

function Describe($w) {
    $parts = @()
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        $name = $child.Current.Name
        if ($name) {
            $parts += ("[{0}] {1}" -f `
                $child.Current.ControlType.ProgrammaticName.Replace('ControlType.', ''), $name)
        }
    }
    return ($parts -join ' | ')
}

function Click($w, [string[]]$names) {
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        $name = ($child.Current.Name -replace '&', '')
        foreach ($wanted in $names) {
            if ($name -eq $wanted) {
                $pattern = $null
                if ($child.TryGetCurrentPattern(
                        [System.Windows.Automation.InvokePattern]::Pattern, [ref]$pattern)) {
                    $pattern.Invoke()
                    Write-Host "clicked '$name'"
                    return $true
                }
            }
        }
    }
    return $false
}

$deadline = (Get-Date).AddMinutes(8)
while ((Get-Date) -lt $deadline) {
    $windows = SetupWindows
    if (-not $windows -or $windows.Count -eq 0) {
        Write-Host 'no setup window left'
        break
    }
    foreach ($w in $windows) {
        Write-Host ("page: '{0}'" -f $w.Current.Name)
        Write-Host ("  " + (Describe $w))
    }
    $clicked = $false
    foreach ($w in $windows) {
        if (Click $w @('Next >', 'Install', 'Finish')) { $clicked = $true; break }
    }
    if (-not $clicked) {
        Write-Host 'nothing to click, waiting'
        Start-Sleep -Seconds 5
    } else {
        Start-Sleep -Seconds 4
    }
}

# The finish page can start the browser.  The user can do that themselves, so
# the box is cleared before the installer is closed.
foreach ($w in SetupWindows) {
    foreach ($child in $w.FindAll([System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition)) {
        if ($child.Current.Name -like '*Launch Paani*') {
            $toggle = $null
            if ($child.TryGetCurrentPattern(
                    [System.Windows.Automation.TogglePattern]::Pattern, [ref]$toggle)) {
                if ($toggle.Current.ToggleState -eq [System.Windows.Automation.ToggleState]::On) {
                    $toggle.Toggle()
                    Write-Host 'cleared the launch checkbox'
                }
            }
        }
    }
}
foreach ($w in SetupWindows) { [void](Click $w @('Finish')) }
Start-Sleep -Seconds 5
Write-Host 'DONE'
