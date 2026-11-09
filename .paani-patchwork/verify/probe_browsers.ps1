$names = 'paani','helium','chrome','brave'
foreach ($n in $names) {
  $procs = Get-CimInstance Win32_Process -Filter "Name='$n.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -notmatch '--type=' }
  foreach ($p in $procs) {
    '{0} pid={1} created={2}' -f $n, $p.ProcessId, $p.CreationDate
    '   exe: ' + $p.ExecutablePath
    $ud = ''
    if ($p.CommandLine -match '--user-data-dir=("[^"]+"|\S+)') { $ud = $Matches[1] }
    '   user-data-dir: ' + $ud
  }
}
'--- extension dirs under each user-data-dir ---'
$roots = @(
  'C:\Users\USER\AppData\Local\Paani\User Data',
  'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify'
)
foreach ($r in $roots) {
  if (-not (Test-Path $r)) { continue }
  Get-ChildItem $r -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $ext = Join-Path $_.FullName 'Extensions'
    if (Test-Path $ext) {
      $ids = (Get-ChildItem $ext -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name) -join ','
      '{0}\{1} -> [{2}]' -f $r, $_.Name, $ids
    }
  }
}
