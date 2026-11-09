$ErrorActionPreference = 'Continue'
$log = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\preflight_backdrop.txt'
Set-Location 'E:\eric\PaaniBrowserChromiumFork\paani-windows'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $log
python build/patchwork/run_ninja.py -C out/Default `
    chrome/browser/ui/views/frame:paani_chrome_backdrop `
    chrome/browser/ui/views/frame:browser_frame_view_win_impl -j 8 -k 0 *>> $log
"EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
