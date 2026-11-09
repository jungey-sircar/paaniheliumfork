param([string]$Profile, [string]$Port)
$ErrorActionPreference = 'Stop'

$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$out = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
$logDir = Join-Path $verify 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# --enable-logging=stderr is what makes the "Paani: ad blocker ..." LOG lines
# land in the .err file; without them the engine diagnostics are only visible
# as rendered text on the page.
$browser = Start-Process -FilePath (Join-Path $out 'paani.exe') `
    -ArgumentList @(
        '--headless=new',
        ('--remote-debugging-port=' + $Port),
        ('--user-data-dir=' + (Join-Path $verify $Profile)),
        '--window-size=1280,800',
        '--enable-logging=stderr',
        '--disable-extensions',
        '--disable-component-extensions-with-background-pages'
    ) -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir ($Profile + '.out')) `
    -RedirectStandardError (Join-Path $logDir ($Profile + '.err'))
Write-Output ('PAANI PID=' + $browser.Id + ' PORT=' + $Port + ' PROFILE=' + $Profile)
