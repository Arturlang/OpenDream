# Per-thread CPU over a window, with the OS thread description (.NET sets it from Thread.Name).
#   threads.ps1 -ProcessId N [-Seconds 20] [-Top 15]
param([int]$ProcessId, [int]$Seconds = 20, [int]$Top = 15)
if (-not ("OdhThr" -as [type])) {
Add-Type @"
using System; using System.Runtime.InteropServices;
public static class OdhThr {
  [DllImport("kernel32.dll")] public static extern IntPtr OpenThread(uint access, bool inherit, uint id);
  [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] public static extern int GetThreadDescription(IntPtr h, out IntPtr desc);
  [DllImport("kernel32.dll")] public static extern IntPtr LocalFree(IntPtr p);
  public static string Name(uint id) {
    IntPtr h = OpenThread(0x0800, false, id); // THREAD_QUERY_LIMITED_INFORMATION
    if (h == IntPtr.Zero) return "";
    try { IntPtr d; if (GetThreadDescription(h, out d) < 0) return ""; var s = Marshal.PtrToStringUni(d); LocalFree(d); return s ?? ""; }
    finally { CloseHandle(h); }
  }
}
"@
}
function Snap { $p = Get-Process -Id $ProcessId; $h = @{}; foreach ($t in $p.Threads) { try { $h[$t.Id] = $t.TotalProcessorTime.TotalMilliseconds } catch {} }; $h }
$a = Snap; Start-Sleep -Seconds $Seconds; $b = Snap
$rows = foreach ($id in $b.Keys) { $d = $b[$id] - ($a[$id] ?? 0); [pscustomobject]@{ Id = $id; Pct = 100 * $d / ($Seconds * 1000); Name = [OdhThr]::Name([uint32]$id) } }
$total = ($rows | Measure-Object Pct -Sum).Sum
"total {0:N1}% of a core over {1}s across {2} threads" -f $total, $Seconds, $rows.Count
$rows | Sort-Object Pct -Descending | Select-Object -First $Top | ForEach-Object { "{0,7:N2}%  tid={1,-6} {2}" -f $_.Pct, $_.Id, $_.Name }
