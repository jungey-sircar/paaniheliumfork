param([string]$Path)

$code = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class Rm {
  const int ERROR_SUCCESS = 0;
  const int CCH_RM_SESSION_KEY = 32;
  const int ERROR_MORE_DATA = 234;

  [StructLayout(LayoutKind.Sequential)]
  public struct RM_UNIQUE_PROCESS {
    public int dwProcessId;
    public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime;
  }

  [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
  public struct RM_PROCESS_INFO {
    public RM_UNIQUE_PROCESS Process;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
    public string strAppName;
    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)]
    public string strServiceShortName;
    public uint ApplicationType;
    public uint AppStatus;
    public uint TSSessionId;
    [MarshalAs(UnmanagedType.Bool)]
    public bool bRestartable;
  }

  [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
  public static extern int RmStartSession(out uint handle, int flags, StringBuilder key);

  [DllImport("rstrtmgr.dll")]
  public static extern int RmEndSession(uint handle);

  [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
  public static extern int RmRegisterResources(uint handle, uint nFiles,
    string[] files, uint nApps, RM_UNIQUE_PROCESS[] apps, uint nServices,
    string[] services);

  [DllImport("rstrtmgr.dll")]
  public static extern int RmGetList(uint handle, out uint nProcInfoNeeded,
    ref uint nProcInfo, [In, Out] RM_PROCESS_INFO[] affectedApps, ref uint rebootReasons);

  public static string WhoLocks(string path) {
    uint handle;
    var key = new StringBuilder(CCH_RM_SESSION_KEY + 1);
    int res = RmStartSession(out handle, 0, key);
    if (res != ERROR_SUCCESS) return "RmStartSession failed: " + res;
    try {
      string[] resources = new string[] { path };
      res = RmRegisterResources(handle, 1, resources, 0, null, 0, null);
      if (res != ERROR_SUCCESS) return "RmRegisterResources failed: " + res;
      uint nProcInfoNeeded = 0, nProcInfo = 0, reboot = 0;
      res = RmGetList(handle, out nProcInfoNeeded, ref nProcInfo, null, ref reboot);
      if (res == ERROR_MORE_DATA) {
        var infos = new RM_PROCESS_INFO[nProcInfoNeeded];
        nProcInfo = nProcInfoNeeded;
        res = RmGetList(handle, out nProcInfoNeeded, ref nProcInfo, infos, ref reboot);
        if (res != ERROR_SUCCESS) return "RmGetList failed: " + res;
        var sb = new StringBuilder();
        for (int i = 0; i < nProcInfo; i++) {
          sb.AppendLine(infos[i].Process.dwProcessId + " " + infos[i].strAppName +
                        " type=" + infos[i].ApplicationType);
        }
        return sb.ToString();
      }
      if (res == ERROR_SUCCESS) return "(no locking process reported)";
      return "RmGetList failed: " + res;
    } finally {
      RmEndSession(handle);
    }
  }
}
'@

Add-Type -TypeDefinition $code -Language CSharp
$full = (Resolve-Path $Path).Path
Write-Output "Locking processes for $full :"
[Rm]::WhoLocks($full)
