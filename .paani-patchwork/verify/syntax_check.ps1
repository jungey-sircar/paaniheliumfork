param([string[]]$Files)
foreach ($f in $Files) {
  $errors = $null
  [System.Management.Automation.Language.Parser]::ParseFile($f, [ref]$null, [ref]$errors) | Out-Null
  if ($errors.Count -eq 0) {
    "OK  $f"
  } else {
    "ERR $f"
    $errors | ForEach-Object { '  line {0}: {1}' -f $_.Extent.StartLineNumber, $_.Message }
  }
}
