param([string]$Path)
$errors = $null
$tokens = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
    foreach ($e in $errors) {
        Write-Output ("SYNTAX ERROR line {0}: {1}" -f $e.Extent.StartLineNumber, $e.Message)
    }
    exit 1
}
Write-Output "SYNTAX OK: $Path"
