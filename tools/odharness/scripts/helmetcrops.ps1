param([int]$OdPid, [int]$ByPid, [string]$OutFile, [int]$OdX, [int]$OdY, [int]$ByX, [int]$ByY)
Add-Type -AssemblyName System.Drawing
. "$PSScriptRoot\..\win32.ps1" -Command 'noop' -ProcessId $OdPid 2>$null
function Grab($procId) {
    $h = Get-MainWindow $procId
    $r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
    $bmp = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
    $g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [OdhWin]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
    return $bmp
}
$od = Grab $OdPid; $by = Grab $ByPid
$c = New-Object Drawing.Bitmap 488, 240; $g = [Drawing.Graphics]::FromImage($c); $g.InterpolationMode = 'NearestNeighbor'; $g.Clear([Drawing.Color]::Magenta)
$g.DrawImage($od, (New-Object Drawing.Rectangle 0, 0, 240, 240), (New-Object Drawing.Rectangle ($OdX - 20), ($OdY - 26), 40, 40), 'Pixel')
$g.DrawImage($by, (New-Object Drawing.Rectangle 248, 0, 240, 240), (New-Object Drawing.Rectangle ($ByX - 20), ($ByY - 26), 40, 40), 'Pixel')
$c.Save($OutFile); "saved $OutFile"
