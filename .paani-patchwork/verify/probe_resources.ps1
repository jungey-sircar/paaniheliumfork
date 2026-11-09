# Free commit charge and free disk on the build volume, read the way the
# machine actually reports them.
$ErrorActionPreference = 'Continue'

$counters = (Get-Counter '\Memory\Committed Bytes', '\Memory\Commit Limit', '\Memory\Available MBytes').CounterSamples
$committed = ($counters | Where-Object { $_.Path -like '*committed bytes' }).CookedValue
$limit = ($counters | Where-Object { $_.Path -like '*commit limit' }).CookedValue
$availMb = ($counters | Where-Object { $_.Path -like '*available mbytes' }).CookedValue

Write-Output ("committed {0:N1} GB of {1:N1} GB" -f ($committed / 1GB), ($limit / 1GB))
Write-Output ("headroom   {0:N1} GB" -f (($limit - $committed) / 1GB))
Write-Output ("available  {0:N0} MB" -f $availMb)

foreach ($d in @('E:\', 'C:\')) {
    $free = (Get-PSDrive -Name $d.Substring(0, 1)).Free
    Write-Output ("free {0}    {1:N1} GB" -f $d, ($free / 1GB))
}
