$ErrorActionPreference = 'Continue'
Add-Type -AssemblyName System.Windows.Forms

'=== top-level windows of browser processes ==='
foreach ($name in 'paani', 'chrome') {
  Get-CimInstance Win32_Process -Filter "Name='$name.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -notmatch '--type=' } |
    ForEach-Object {
      $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
      if ($p) {
        '{0} pid={1} title="{2}"' -f $name, $p.Id, $p.MainWindowTitle
      }
    }
}

'=== uBlock Origin in Google Chrome profiles ==='
$chromeRoot = 'C:\Users\USER\AppData\Local\Google\Chrome\User Data'
Get-ChildItem $chromeRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $ext = Join-Path $_.FullName 'Extensions'
  if (Test-Path $ext) {
    $ids = Get-ChildItem $ext -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
    if ($ids) { '{0} -> {1}' -f $_.Name, ($ids -join ', ') }
  }
}

'=== uBlock Origin in Paani profiles ==='
$paaniRoot = 'C:\Users\USER\AppData\Local\Paani\User Data'
Get-ChildItem $paaniRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $ext = Join-Path $_.FullName 'Extensions'
  if (Test-Path $ext) {
    $ids = Get-ChildItem $ext -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
    '{0} -> [{1}]' -f $_.Name, ($ids -join ', ')
  } else {
    '{0} -> no Extensions folder' -f $_.Name
  }
}

'=== paani prefs: extensions + built-in blocker state ==='
$prefs = Join-Path $paaniRoot 'Default\Preferences'
if (Test-Path $prefs) {
  $txt = Get-Content $prefs -Raw
  'Preferences length: ' + $txt.Length
  if ($txt -match 'cjpalhdlnbpafiamejdnhcphjbkeiagm') { 'uBlock id found in Paani Preferences' } else { 'no uBlock id in Paani Preferences' }
  $m = [regex]::Matches($txt, '"paani[^"]{0,60}":\s*[^,}]{0,60}')
  foreach ($x in $m) { 'pref ' + $x.Value }
}
