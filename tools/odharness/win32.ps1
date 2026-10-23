# Win32 helpers for driving DreamSeeker and the OpenDream client side by side.
#   win32.ps1 tree   -ProcessId N                      child-window tree (class, text, client-relative rect)
#   win32.ps1 place  -ProcessId N -W 1600 -H 900       restore + move the main window to 0,0 at WxH (outer size)
#   win32.ps1 shot   -ProcessId N -Out file.png        PrintWindow capture of the main window
#   win32.ps1 click  -ProcessId N -X x -Y y [-Button right] [-Double]
#                                                      click at client-area coords of the main window (real input)
#   win32.ps1 windows -ProcessId N                     visible top-level windows (popups too)
#   win32.ps1 hold -ProcessId N -Vk 0x44 -Ms 1500       hold a key (with auto-repeat) in the target window
#   win32.ps1 dlg    -ProcessId N                      the open prompt dialog's controls as JSON
#   win32.ps1 dlgdo  -ProcessId N -Seq "press`tOK"      answer it: text|select|press|submit|close, TAB, argument
#   any command takes -Title substr to target a popup instead of the largest window
#   win32.ps1 key    -ProcessId N -Keys "text{ENTER}"  focus the window and send keys (SendKeys syntax)
param(
    [Parameter(Position = 0)][string]$Command,
    [int]$ProcessId,
    [int]$W, [int]$H,
    [int]$X, [int]$Y,
    [string]$Button = "left",
    [switch]$Double,
    [string]$Out,
    [string]$Keys,
    [string]$Title = "",
    [int]$Vk = 0,
    [int]$Ms = 1000,
    [string]$Seq = ""
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Drawing, System.Windows.Forms
if (-not ("OdhWin" -as [type])) {
Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public static class OdhWin {
  public delegate bool P(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(P p, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, P p, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr h);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint mapType);
  [DllImport("user32.dll")] public static extern IntPtr ChildWindowFromPointEx(IntPtr parent, POINT p, uint flags);
  [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr h, ref POINT p);
  // Deepest visible child under a screen point, so a message reaches the control that would get a real click
  public static IntPtr Deepest(IntPtr top, int sx, int sy) {
    IntPtr cur = top;
    while (true) {
      var p = new POINT { X = sx, Y = sy };
      ScreenToClient(cur, ref p);
      IntPtr child = ChildWindowFromPointEx(cur, p, 1 | 4); // skip invisible, skip transparent
      if (child == IntPtr.Zero || child == cur) return cur;
      cur = child;
    }
  }
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
  public static List<IntPtr> TopLevel(uint target) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint pid; GetWindowThreadProcessId(h, out pid); if (pid == target && IsWindowVisible(h)) r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
  public static List<IntPtr> Children(IntPtr parent) {
    var r = new List<IntPtr>();
    EnumChildWindows(parent, (h, l) => { r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
  public static string Text(IntPtr h) { var s = new StringBuilder(512); GetWindowText(h, s, 512); return s.ToString(); }
  public static string Class(IntPtr h) { var s = new StringBuilder(256); GetClassName(h, s, 256); return s.ToString(); }
}
// Reads and drives standard dialog controls with messages, so no focus or real input is needed
public static class OdhDlg {
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, StringBuilder l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetWindowLong(IntPtr h, int i);
  public static string GetText(IntPtr h) {
    int n = (int)SendMessage(h, 0x0E, IntPtr.Zero, IntPtr.Zero);
    var s = new StringBuilder(n + 1); SendMessage(h, 0x0D, (IntPtr)(n + 1), s); return s.ToString();
  }
  public static string Item(IntPtr h, int i, bool combo) {
    int n = (int)SendMessage(h, combo ? 0x149u : 0x18Au, (IntPtr)i, IntPtr.Zero);
    var s = new StringBuilder(n + 1); SendMessage(h, combo ? 0x148u : 0x189u, (IntPtr)i, s); return s.ToString();
  }
  public static int Count(IntPtr h, bool combo) { return (int)SendMessage(h, combo ? 0x146u : 0x18Bu, IntPtr.Zero, IntPtr.Zero); }
  public static int Selected(IntPtr h, bool combo) { return (int)SendMessage(h, combo ? 0x147u : 0x188u, IntPtr.Zero, IntPtr.Zero); }
  public static void Select(IntPtr dlg, IntPtr h, int i, bool combo) {
    SendMessage(h, combo ? 0x14Eu : 0x186u, (IntPtr)i, IntPtr.Zero);
    SendMessage(dlg, 0x111, (IntPtr)((1 << 16) | (GetDlgCtrlID(h) & 0xFFFF)), h);
  }
  public static void Click(IntPtr dlg, IntPtr button) {
    SendMessage(dlg, 0x111, (IntPtr)(GetDlgCtrlID(button) & 0xFFFF), button);
  }
  public static bool IsDefault(IntPtr button) { return (GetWindowLong(button, -16) & 0xF) == 1; }
}
"@
}
# Physical pixels everywhere, so sizes match what the engines report.
[OdhWin]::SetProcessDPIAware() | Out-Null

function Get-MainWindow([int]$procId) {
    $best = $null; $bestArea = -1
    foreach ($h in [OdhWin]::TopLevel([uint32]$procId)) {
        $t = [OdhWin]::Text($h)
        if ($Title -eq '<empty>') { if ($t -ne '') { continue } }
        elseif ($Title -and $t -notlike "*$Title*") { continue }
        $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
        $area = ($r.R - $r.L) * ($r.B - $r.T)
        if ($area -gt $bestArea) { $best = $h; $bestArea = $area }
    }
    if (-not $best) { throw "process $procId has no visible window" }
    return $best
}

function Get-ClientOrigin($hwnd) {
    $p = New-Object OdhWin+POINT
    [OdhWin]::ClientToScreen($hwnd, [ref]$p) | Out-Null
    return $p
}

function Get-Dialog([int]$procId) {
    # A prompt can be larger than the main window, so pick it by the standard dialog class
    foreach ($h in [OdhWin]::TopLevel([uint32]$procId)) {
        if ([OdhWin]::Class($h) -eq '#32770') { return $h }
    }
    throw "process $procId has no dialog open"
}

function Get-DialogControls($dlg) {
    foreach ($h in [OdhWin]::Children($dlg)) {
        if ([OdhWin]::IsWindowVisible($h)) { [pscustomobject]@{ H = $h; Class = [OdhWin]::Class($h) } }
    }
}

if ($Command -eq 'dlg' -or $Command -eq 'dlgdo') {
    $dlg = Get-Dialog $ProcessId
    $controls = @(Get-DialogControls $dlg)
    $buttons = @($controls | Where-Object { $_.Class -eq 'Button' })
    $edit = $controls | Where-Object { $_.Class -match 'Edit' } | Select-Object -First 1
    $list = $controls | Where-Object { $_.Class -match 'ListBox|ComboBox' } | Select-Object -First 1
    if ($Command -eq 'dlg') {
        $o = [ordered]@{
            hwnd = [int64]$dlg
            title = [OdhWin]::Text($dlg)
            message = (@($controls | Where-Object { $_.Class -eq 'Static' } | ForEach-Object { [OdhWin]::Text($_.H) } | Where-Object { $_ }) -join "`n")
            buttons = @($buttons | ForEach-Object { [OdhWin]::Text($_.H) })
            default_button = ($buttons | Where-Object { [OdhDlg]::IsDefault($_.H) } | ForEach-Object { [OdhWin]::Text($_.H) } | Select-Object -First 1)
            text = $(if ($edit) { [OdhDlg]::GetText($edit.H) } else { $null })
            items = $null
            selected = $null
            classes = @($controls | ForEach-Object { $_.Class })
        }
        if ($list) {
            $combo = $list.Class -match 'ComboBox'
            $o.items = @(0..([OdhDlg]::Count($list.H, $combo) - 1) | Where-Object { $_ -ge 0 } | ForEach-Object { [OdhDlg]::Item($list.H, $_, $combo) })
            $o.selected = [OdhDlg]::Selected($list.H, $combo)
        }
        $o | ConvertTo-Json -Compress -Depth 4
        exit 0
    }
    $action, $arg = $Seq -split "`t", 2
    switch ($action) {
        'text' {
            if (-not $edit) { throw "dialog has no edit control" }
            [OdhDlg]::SendMessage($edit.H, 0x0C, [IntPtr]::Zero, [string]$arg) | Out-Null
            "text set"
        }
        'select' {
            if (-not $list) { throw "dialog has no list" }
            [OdhDlg]::Select($dlg, $list.H, [int]$arg, ($list.Class -match 'ComboBox'))
            "selected"
        }
        'press' {
            $b = $buttons | Where-Object { ([OdhWin]::Text($_.H) -replace '&', '') -eq $arg } | Select-Object -First 1
            if (-not $b) { throw "no button '$arg'" }
            [OdhDlg]::Click($dlg, $b.H)
            "pressed"
        }
        'submit' {
            $b = $buttons | Where-Object { [OdhDlg]::IsDefault($_.H) } | Select-Object -First 1
            if ($b) { [OdhDlg]::Click($dlg, $b.H) } else { [OdhDlg]::SendMessage($dlg, 0x111, [IntPtr]1, [IntPtr]::Zero) | Out-Null }
            "submitted"
        }
        'close' {
            [OdhWin]::PostMessage($dlg, 0x10, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
            "closed"
        }
        default { throw "unknown dialog action '$action'" }
    }
    exit 0
}

$main = Get-MainWindow $ProcessId
switch ($Command) {
    'windows' {
        foreach ($h in [OdhWin]::TopLevel([uint32]$ProcessId)) {
            $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
            "'$([OdhWin]::Text($h))' $($r.R - $r.L)x$($r.B - $r.T) at $($r.L),$($r.T)"
        }
    }
    'tree' {
        $o = Get-ClientOrigin $main
        $c = New-Object OdhWin+RECT; [OdhWin]::GetClientRect($main, [ref]$c) | Out-Null
        "main '$([OdhWin]::Text($main))' client=$($c.R)x$($c.B)"
        foreach ($h in [OdhWin]::Children($main)) {
            if (-not [OdhWin]::IsWindowVisible($h)) { continue }
            $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
            $depth = 0; $p = [OdhWin]::GetParent($h)
            while ($p -ne [IntPtr]::Zero -and $p -ne $main) { $depth++; $p = [OdhWin]::GetParent($p) }
            $text = [OdhWin]::Text($h); if ($text.Length -gt 40) { $text = $text.Substring(0, 40) }
            "{0}{1} '{2}' pos={3},{4} size={5}x{6}" -f ('  ' * $depth), [OdhWin]::Class($h), $text, ($r.L - $o.X), ($r.T - $o.Y), ($r.R - $r.L), ($r.B - $r.T)
        }
    }
    'place' {
        [OdhWin]::ShowWindow($main, 9) | Out-Null
        [OdhWin]::MoveWindow($main, $X, $Y, $W, $H, $true) | Out-Null
        Start-Sleep -Milliseconds 1000
        $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($main, [ref]$r) | Out-Null
        $c = New-Object OdhWin+RECT; [OdhWin]::GetClientRect($main, [ref]$c) | Out-Null
        "outer=$($r.R - $r.L)x$($r.B - $r.T) client=$($c.R)x$($c.B)"
    }
    'shot' {
        $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($main, [ref]$r) | Out-Null
        $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
        $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
        [OdhWin]::PrintWindow($main, $dc, 2) | Out-Null
        $g.ReleaseHdc($dc); $bmp.Save($Out); $g.Dispose(); $bmp.Dispose()
        "$($r.R - $r.L)x$($r.B - $r.T) -> $Out"
    }
    'click' {
        # Real input (SDL ignores posted button messages), but only when the target pixel provably belongs to the
        # target process: a click must never land in whatever other window happens to be on top.
        $o = Get-ClientOrigin $main
        $sx = $o.X + $X; $sy = $o.Y + $Y
        [OdhWin]::ShowWindow($main, 9) | Out-Null
        [OdhWin]::SetForegroundWindow($main) | Out-Null
        Start-Sleep -Milliseconds 200
        $pt = New-Object OdhWin+POINT; $pt.X = $sx; $pt.Y = $sy
        $hit = [OdhWin]::WindowFromPoint($pt)
        $hitPid = 0; [OdhWin]::GetWindowThreadProcessId($hit, [ref]$hitPid) | Out-Null
        if ($hitPid -ne $ProcessId) {
            $owner = (Get-Process -Id $hitPid -ErrorAction SilentlyContinue).ProcessName
            throw "refusing to click: screen $sx,$sy is covered by $owner (pid $hitPid), not the target window. Bring it to the front or free that area."
        }
        [OdhWin]::SetCursorPos($sx, $sy) | Out-Null
        Start-Sleep -Milliseconds 80
        $down, $up = if ($Button -eq 'right') { 0x8, 0x10 } else { 0x2, 0x4 }
        foreach ($i in 1..($(if ($Double) { 2 } else { 1 }))) {
            [OdhWin]::mouse_event($down, 0, 0, 0, [UIntPtr]::Zero)
            Start-Sleep -Milliseconds 40
            [OdhWin]::mouse_event($up, 0, 0, 0, [UIntPtr]::Zero)
            Start-Sleep -Milliseconds 60
        }
        "clicked $Button at client $X,$Y (screen $sx,$sy, verified target pid)"
    }
    'key' {
        [OdhWin]::SetForegroundWindow($main) | Out-Null
        Start-Sleep -Milliseconds 200
        $fgPid = 0; [OdhWin]::GetWindowThreadProcessId([OdhWin]::GetForegroundWindow(), [ref]$fgPid) | Out-Null
        if ($fgPid -ne $ProcessId) { throw "refusing to type: the foreground window belongs to pid $fgPid, not the target" }
        [System.Windows.Forms.SendKeys]::SendWait($Keys)
        "sent keys"
    }
    'hold' {
        # Real key down, held for -Ms milliseconds (the OS auto-repeats it like a person holding it), then up.
        # Only when the target really is the foreground window, so the keys never go anywhere else.
        [OdhWin]::ShowWindow($main, 9) | Out-Null
        [OdhWin]::SetForegroundWindow($main) | Out-Null
        Start-Sleep -Milliseconds 250
        $fgPid = 0; [OdhWin]::GetWindowThreadProcessId([OdhWin]::GetForegroundWindow(), [ref]$fgPid) | Out-Null
        if ($fgPid -ne $ProcessId) { throw "refusing to press keys: the foreground window belongs to pid $fgPid, not the target" }
        $scan = [byte][OdhWin]::MapVirtualKey([uint32]$Vk, 0)
        [OdhWin]::keybd_event([byte]$Vk, $scan, 0, [UIntPtr]::Zero)
        # keybd_event sends a single down; repeat downs every 33 ms like Windows auto-repeat does for a held key
        $end = (Get-Date).AddMilliseconds($Ms); Start-Sleep -Milliseconds 300
        while ((Get-Date) -lt $end) { [OdhWin]::keybd_event([byte]$Vk, $scan, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 33 }
        [OdhWin]::keybd_event([byte]$Vk, $scan, 2, [UIntPtr]::Zero)   # KEYEVENTF_KEYUP
        "held vk=$Vk for $Ms ms"
    }
    'seq' {
        # A key script: "D+" presses D, "D-" releases it, a bare number waits that many ms. While waiting, the most
        # recently pressed key that is still held auto-repeats every 33 ms, as Windows does for a held key.
        [OdhWin]::ShowWindow($main, 9) | Out-Null
        [OdhWin]::SetForegroundWindow($main) | Out-Null
        Start-Sleep -Milliseconds 250
        $fgPid = 0; [OdhWin]::GetWindowThreadProcessId([OdhWin]::GetForegroundWindow(), [ref]$fgPid) | Out-Null
        if ($fgPid -ne $ProcessId) { throw "refusing to press keys: the foreground window belongs to pid $fgPid, not the target" }
        $held = [System.Collections.Generic.List[int]]::new()
        foreach ($tok in ($Seq -split ' ' | Where-Object { $_ })) {
            if ($tok -match '^[0-9]+$') {
                $end = (Get-Date).AddMilliseconds([int]$tok)
                while ((Get-Date) -lt $end) {
                    if ($held.Count) {
                        $rv = $held[$held.Count - 1]
                        [OdhWin]::keybd_event([byte]$rv, [byte][OdhWin]::MapVirtualKey([uint32]$rv, 0), 0, [UIntPtr]::Zero)
                    }
                    Start-Sleep -Milliseconds 33
                }
            } elseif ($tok -match '^(.+)([+-])$') {
                $name = $Matches[1]
                $kv = if ($name.Length -eq 1) { [int][char]$name.ToUpper() } else { [Convert]::ToInt32($name, 16) }
                $scan = [byte][OdhWin]::MapVirtualKey([uint32]$kv, 0)
                $held.Remove($kv) | Out-Null
                if ($Matches[2] -eq '+') {
                    [OdhWin]::keybd_event([byte]$kv, $scan, 0, [UIntPtr]::Zero)
                    $held.Add($kv)
                } else {
                    [OdhWin]::keybd_event([byte]$kv, $scan, 2, [UIntPtr]::Zero)
                }
            }
        }
        foreach ($kv in @($held)) { [OdhWin]::keybd_event([byte]$kv, [byte][OdhWin]::MapVirtualKey([uint32]$kv, 0), 2, [UIntPtr]::Zero) }
        "played: $Seq"
    }
    'noop' { }
    default { throw "unknown command '$Command'" }
}
