$ErrorActionPreference = 'Stop'
$verify = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
$out = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
$logDir = Join-Path $verify 'logs'
$profile = Join-Path $verify 'profile4'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$server = Start-Process -FilePath 'C:\Python313\python.exe' `
    -ArgumentList @('-m', 'http.server', '8731', '--bind', '127.0.0.1') `
    -WorkingDirectory (Join-Path $verify 'www') -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir 'warm_http.out') `
    -RedirectStandardError (Join-Path $logDir 'warm_http.err')
Write-Output ('HTTP PID=' + $server.Id)

$browser = Start-Process -FilePath (Join-Path $out 'paani.exe') `
    -ArgumentList @(
        '--headless=new',
        '--remote-debugging-port=9334',
        ('--user-data-dir=' + $profile),
        '--window-size=1280,800',
        '--disable-extensions',
        '--disable-component-extensions-with-background-pages',
        '--disable-features=Translate'
    ) -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $logDir 'warm_paani.out') `
    -RedirectStandardError (Join-Path $logDir 'warm_paani.err')
Write-Output ('PAANI PID=' + $browser.Id)
