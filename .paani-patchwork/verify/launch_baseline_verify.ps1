$ErrorActionPreference = 'Stop'
$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$bin = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\baseline_run\Helium-bin'
$logDir = Join-Path $verify 'logs'
$profile = Join-Path $verify 'profile_base'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$browser = Start-Process -FilePath (Join-Path $bin 'chrome.exe') `
    -ArgumentList @(
        '--headless=new',
        '--remote-debugging-port=9335',
        ('--user-data-dir=' + $profile),
        '--window-size=1280,800',
        '--disable-extensions',
        '--disable-component-extensions-with-background-pages'
    ) -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir 'base_paani.out') `
    -RedirectStandardError (Join-Path $logDir 'base_paani.err')
Write-Output ('BASELINE PID=' + $browser.Id)
Write-Output ('EXE=' + (Join-Path $bin 'chrome.exe'))
