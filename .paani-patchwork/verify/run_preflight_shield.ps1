$ErrorActionPreference = 'Continue'
# A fresh log per run: two overlapping runs writing one file is how a stale
# result looks like a fresh one.
$stamp = Get-Date -Format 'HHmmss'
$log = "E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\preflight_shield_$stamp.txt"
Write-Output "LOG=$log"
Set-Location 'E:\eric\PaaniBrowserChromiumFork\paani-windows'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $log

# Copy the staged Paani overlay into the Chromium tree exactly like build.py does,
# so the preflight compiles the same files the real build will.
python -c "import build; from pathlib import Path; build._copy_paani_sources(Path('build/src'))" `
    *>&1 | Out-File -Append -Encoding utf8 $log
"COPY EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log

python build/patchwork/run_ninja.py -C out/Default `
    chrome/browser/paani/adblock:paani_adblock `
    chrome/browser/ui/views/toolbar:impl `
    chrome/browser:browser -j 8 -k 0 `
    *>&1 | Out-File -Append -Encoding utf8 $log
"EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
Write-Output "DONE EXIT=$LASTEXITCODE LOG=$log"
