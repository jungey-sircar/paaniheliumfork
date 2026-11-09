$ErrorActionPreference = 'Continue'
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WinEnum2 {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetWindowTextLengthW(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  static EnumProc kept;
  public static List<string> Titles() {
    var list = new List<string>();
    kept = delegate (IntPtr h, IntPtr l) {
      try {
        if (!IsWindowVisible(h)) return true;
        int n = GetWindowTextLengthW(h);
        if (n == 0) return true;
        var sb = new StringBuilder(n + 1);
        if (GetWindowTextW(h, sb, n + 1) == 0) return true;
        uint pid; GetWindowThreadProcessId(h, out pid);
        list.Add(pid + "|" + sb.ToString());
      } catch { }
      return true;
    };
    EnumWindows(kept, IntPtr.Zero);
    return list;
  }
}
"@
$targets = @{}
foreach ($n in 'paani', 'chrome', 'helium') {
  Get-CimInstance Win32_Process -Filter "Name='$n.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -notmatch '--type=' } |
    ForEach-Object { $targets[[string]$_.ProcessId] = $n }
}
$out = [WinEnum2]::Titles()
'browser windows:'
foreach ($t in $out) {
  $parts = $t.Split('|', 2)
  if ($targets.ContainsKey($parts[0])) {
    '{0,-7} pid={1,-6} {2}' -f $targets[$parts[0]], $parts[0], $parts[1]
  }
}
'total visible titled windows: ' + $out.Count
