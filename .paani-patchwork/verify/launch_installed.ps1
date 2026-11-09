# Launches the *installed* Paani (not the build tree) for verification.
param([string]$Profile = 'installed', [string]$Port = '9342')
$ErrorActionPreference = 'Stop'

$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$app = Join-Path $env:LOCALAPPDATA 'Paani\Application'
$logDir = Join-Path $verify 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$browser = Start-Process -FilePath (Join-Path $app 'paani.exe') `
    -ArgumentList @(
        '--headless=new',
        ('--remote-debugging-port=' + $Port),
        ('--user-data-dir=' + (Join-Path $verify $Profile)),
        '--window-size=1280,800',
        '--enable-logging=stderr'
    ) -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir ($Profile + '.out')) `
    -RedirectStandardError (Join-Path $logDir ($Profile + '.err'))
Write-Output ('INSTALLED PAANI PID=' + $browser.Id + ' PORT=' + $Port + ' FROM=' + $app)
