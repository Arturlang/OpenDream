param([int]$OdPid, [int]$ByPid, [int]$N = 12)
Add-Type -AssemblyName System.Drawing
. "$PSScriptRoot\..\win32.ps1" -Command 'noop' -ProcessId $OdPid 2>$null
# topmost row in the middle sprite's column whose colour is bright (the ghost) - lower number = higher jump
function TopOf($procId, $x0, $x1, $y0, $y1) {
    $h = Get-MainWindow $procId
    $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
    $bmp = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
    $g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [OdhWin]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
    for ($y = $y0; $y -lt $y1; $y++) { for ($x = $x0; $x -lt $x1; $x += 2) { $c = $bmp.GetPixel($x, $y); if ($c.R -gt 200 -and $c.G -gt 200) { $bmp.Dispose(); return $y } } }
    $bmp.Dispose(); return -1
}
$t0 = Get-Date
for ($i = 0; $i -lt $N; $i++) {
    $od = TopOf $OdPid 140 185 180 360
    $by = TopOf $ByPid 150 195 150 330
    "{0,5:N1}s  OD top={1,4}  BYOND top={2,4}" -f ((Get-Date) - $t0).TotalSeconds, $od, $by
    Start-Sleep -Milliseconds 350
}
