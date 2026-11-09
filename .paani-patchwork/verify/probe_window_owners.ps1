$ErrorActionPreference = 'Continue'
Add-Type @"
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
public class WinEnum {
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern int GetWindowTextLengthW(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  delegate bool EnumProc(IntPtr h, IntPtr l);
  public static List<string> Titles() {
    var list = new List<string>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      int n = GetWindowTextLengthW(h);
      if (n == 0) return true;
      var sb = new StringBuilder(n + 2);
      GetWindowTextW(h, sb, sb.Capacity);
      uint pid; GetWindowThreadProcessId(h, out pid);
      list.Add(pid + "|" + sb.ToString());
      return true;
    }, IntPtr.Zero);
    return list;
  }
}
"@
$targets = @{}
foreach ($n in 'paani', 'chrome') {
  Get-CimInstance Win32_Process -Filter "Name='$n.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -notmatch '--type=' } |
    ForEach-Object { $targets[[string]$_.ProcessId] = $n }
}
foreach ($t in [WinEnum]::Titles()) {
  $parts = $t.Split('|', 2)
  if ($targets.ContainsKey($parts[0])) {
    '{0,-7} pid={1,-6} {2}' -f $targets[$parts[0]], $parts[0], $parts[1]
  }
}
