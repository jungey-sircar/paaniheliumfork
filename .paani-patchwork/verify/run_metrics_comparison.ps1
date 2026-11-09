# Runs the eleven metrics for Paani and for the Helium baseline and writes
# the comparison table.
#
# Helium is measured twice. Once exactly as it ships, with its uBlock Origin
# component extension enabled, which is what a user of upstream Helium gets.
# And once with that extension switched off, so that the comparison against
# Paani is between two blocking engines rather than between an engine and an
# extension. Paani itself has no ad blocking extension at all: it blocks with
# its own engine, built into the browser.
param(
    [string]$PaaniExe = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default\paani.exe',
    [string]$HeliumExe = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\baseline\Helium-bin\chrome.exe',
    [string]$Root = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify',
    [string]$ProbeUrl = 'https://www.foxnews.com/politics'
)
$ErrorActionPreference = 'Continue'
$py = 'C:\Python313\python.exe'
$measure = Join-Path $Root 'measure_metrics.py'
$compare = Join-Path $Root 'compare_metrics.py'
$logs = Join-Path $Root 'logs'

$noUblock = '--disable-component-extensions-with-background-pages'

Write-Host '=== Helium baseline, as it ships (uBlock Origin component enabled) ==='
& $py $measure `
    --exe $HeliumExe --label helium-shipped `
    --profile (Join-Path $Root 'profile_metrics_helium_shipped') `
    --port 9410 --base-port 8711 `
    --out (Join-Path $logs 'metrics_helium_shipped.json') `
    2>&1 | Out-File -Encoding utf8 (Join-Path $logs 'metrics_helium_shipped.out')
Write-Host "exit=$LASTEXITCODE"

Write-Host '=== Helium baseline, blocker off ==='
& $py $measure `
    --exe $HeliumExe --label helium `
    --profile (Join-Path $Root 'profile_metrics_helium') `
    --port 9411 --base-port 8741 `
    --extra-args $noUblock `
    --out (Join-Path $logs 'metrics_helium.json') `
    2>&1 | Out-File -Encoding utf8 (Join-Path $logs 'metrics_helium.out')
Write-Host "exit=$LASTEXITCODE"

Write-Host '=== Paani ==='
# No --disable-component-extensions flag here: Paani does not ship the uBlock
# Origin component at all, so there is nothing to switch off, and passing the
# flag would also switch off the Chrome Web Store component and measure a
# browser that is not the one that ships.
& $py $measure `
    --exe $PaaniExe --label paani `
    --profile (Join-Path $Root 'profile_metrics_paani') `
    --port 9412 --base-port 8761 `
    --blocking-probe-url $ProbeUrl `
    --out (Join-Path $logs 'metrics_paani.json') `
    2>&1 | Out-File -Encoding utf8 (Join-Path $logs 'metrics_paani.out')
Write-Host "exit=$LASTEXITCODE"

Write-Host '=== comparison ==='
& $py $compare `
    --paani (Join-Path $logs 'metrics_paani.json') `
    --baseline (Join-Path $logs 'metrics_helium.json') `
    --baseline-shipped (Join-Path $logs 'metrics_helium_shipped.json') `
    --out 'E:\eric\PaaniBrowserChromiumFork\docs\PAANI-PERFORMANCE.md'
Write-Host "exit=$LASTEXITCODE"
