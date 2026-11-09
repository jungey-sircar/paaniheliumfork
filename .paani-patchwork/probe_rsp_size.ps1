$out = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
$rsp = Get-Content -LiteralPath (Join-Path $out 'chrome.dll.rsp')
$objs = @()
$libs = @()
$imported = 0
foreach ($line in $rsp) {
    $t = $line.Trim().Trim('"')
    if (-not $t) { continue }
    if ($t.StartsWith('-') -or $t.StartsWith('/')) { continue }
    if ($t -match '\.(obj|a|lib)$') {
        $p = Join-Path $out $t
        if (Test-Path -LiteralPath $p) { $objs += (Get-Item -LiteralPath $p).Length }
        else { $imported++ }
    }
}
$bytes = ($objs | Measure-Object -Sum).Sum
Write-Output ('OBJECTS count=' + $objs.Count + ' totalGB=' + [math]::Round($bytes/1GB,2) + ' missingFromTree=' + $imported)
Write-Output ('RSP lines=' + $rsp.Count)
