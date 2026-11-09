$ErrorActionPreference = 'Stop'
$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$out = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
$logDir = Join-Path $verify 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# A local origin so the ad requests are genuinely third-party subresources.
# Port 8000 is taken by splunkd on this box and 8xxx above is in the Winsock
# exclusion list, hence 8731.
$server = Start-Process -FilePath 'C:\Python313\python.exe' `
    -ArgumentList @('-m', 'http.server', '8731', '--bind', '127.0.0.1') `
    -WorkingDirectory (Join-Path $verify 'www') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir 'http.out') `
    -RedirectStandardError (Join-Path $logDir 'http.err')
Write-Output ('HTTP PID=' + $server.Id)

# The bundled uBlock Origin component extension has to be off, otherwise a
# blocked request proves nothing about the Paani engine.
$browser = Start-Process -FilePath (Join-Path $out 'paani.exe') `
    -ArgumentList @(
        '--headless=new',
        '--remote-debugging-port=9333',
        ('--user-data-dir=' + (Join-Path $verify 'profile')),
        '--window-size=1280,800',
        '--disable-extensions',
        '--disable-component-extensions-with-background-pages'
    ) -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir 'paani.out') `
    -RedirectStandardError (Join-Path $logDir 'paani.err')
Write-Output ('PAANI PID=' + $browser.Id)
