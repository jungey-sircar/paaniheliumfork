# Preflight for the allowlist change.
#
# The change is in the URL loader factory: the allowlist is now also checked
# against the page the request was made on, so a site on the allowlist is
# really left alone. The WebUI text changed with it.
#
# Only the two targets that carry the change are compiled here. The full
# build is what relinks paani.dll, and that is the expensive step.
$ErrorActionPreference = 'Continue'
$log = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\preflight_allowlist.txt'
Set-Location 'E:\eric\PaaniBrowserChromiumFork\paani-windows'
"START $(Get-Date -Format o)" | Out-File -Encoding utf8 $log

# Copy the staged Paani overlay into the Chromium tree exactly like build.py
# does, so the preflight compiles the same files the real build will.
python -c "import build; from pathlib import Path; build._copy_paani_sources(Path('build/src'))" `
    *>&1 | Out-File -Append -Encoding utf8 $log
"COPY EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log

python build/patchwork/run_build.py -j 8 -k 0 -C out/Default `
    chrome/browser/paani/adblock:paani_adblock `
    chrome/browser/resources/paani:resources `
    *>&1 | Out-File -Append -Encoding utf8 $log
"EXIT=$LASTEXITCODE $(Get-Date -Format o)" | Out-File -Append -Encoding utf8 $log
