param([int]$ProcId = 15820, [string]$Out = 'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs\live_paani.png')
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -Namespace Live -Name Win -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out R r);
public struct R { public int L,T,Rr,B; }
'@
$p = Get-Process -Id $ProcId -ErrorAction Stop
$h = $p.MainWindowHandle
if ($h -eq [IntPtr]::Zero) { 'NO WINDOW HANDLE for pid ' + $ProcId; exit 1 }
$r = New-Object Live.Win+R
[void][Live.Win]::GetWindowRect($h, [ref]$r)
$w = $r.Rr - $r.L; $ht = $r.B - $r.T
'window rect ' + $r.L + ',' + $r.T + ' ' + $w + 'x' + $ht
$bmp = New-Object System.Drawing.Bitmap $w, $ht
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($r.L, $r.T, 0, 0, (New-Object System.Drawing.Size $w, $ht))
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
'saved ' + $Out
