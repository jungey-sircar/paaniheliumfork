$ErrorActionPreference = 'Stop'
$out = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default'
foreach ($name in 'paani.exe', 'paani.dll', 'paani_proxy.exe', 'setup.exe', 'mini_installer.exe') {
    $p = Join-Path $out $name
    if (-not (Test-Path $p)) { Write-Output ($name + ': MISSING'); continue }
    $v = (Get-Item $p).VersionInfo
    Write-Output ('=== ' + $name + ' sizeMB=' + [math]::Round((Get-Item $p).Length / 1MB, 1))
    Write-Output ('  FileDescription = ' + $v.FileDescription)
    Write-Output ('  ProductName     = ' + $v.ProductName)
    Write-Output ('  OriginalName    = ' + $v.OriginalFileName)
    Write-Output ('  InternalName    = ' + $v.InternalName)
    Write-Output ('  Version         = ' + $v.FileVersion + ' / ' + $v.ProductVersion)
}
$b = 'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\baseline_helium'
if (Test-Path $b) {
    Get-ChildItem -Path $b -Recurse -Filter 'chrome.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 | ForEach-Object {
        $hv = $_.VersionInfo
        Write-Output ('=== baseline chrome.exe for comparison')
        Write-Output ('  ProductName = ' + $hv.ProductName + '  Version = ' + $hv.FileVersion)
    }
}
