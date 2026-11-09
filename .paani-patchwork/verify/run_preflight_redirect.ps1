$ErrorActionPreference = 'Continue'
$log = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\preflight_redirect.txt'
Set-Location 'E:\eric\PaaniBrowserChromiumFork\paani-windows'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $log

# Copy the staged Paani overlay into the Chromium tree exactly like build.py does,
# so the preflight compiles the same files the real build will.
python -c "import build; from pathlib import Path; build._copy_paani_sources(Path('build/src'))" `
    *>&1 | Out-File -Append -Encoding utf8 $log
"COPY EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log

python build/patchwork/run_ninja.py -C out/Default `
    chrome/browser/paani/adblock:paani_adblock `
    chrome/browser/paani/adblock:paani_adblock_rust -j 8 -k 0 `
    *>&1 | Out-File -Append -Encoding utf8 $log
"EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
