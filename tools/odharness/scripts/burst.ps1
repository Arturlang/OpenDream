param([int]$ProcessId, [string]$OutFile, [int]$Frames = 16, [int]$CropX, [int]$CropY, [int]$CropW = 80, [int]$CropH = 110, [string]$Press = "")
Add-Type -AssemblyName System.Drawing
. "$PSScriptRoot\..\win32.ps1" -Command 'noop' -ProcessId $ProcessId 2>$null
# press the key script, then grab frames as fast as PrintWindow allows and lay them out in a strip
$h = Get-MainWindow $ProcessId
[OdhWin]::SetForegroundWindow($h) | Out-Null; Start-Sleep -Milliseconds 300
$r = New-Object OdhWin+RECT; [OdhWin]::GetWindowRect($h, [ref]$r) | Out-Null
$strip = New-Object Drawing.Bitmap ($CropW * $Frames), $CropH
$gs = [Drawing.Graphics]::FromImage($strip)
if ($Press) { $vk = [int][char]$Press.ToUpper(); [OdhWin]::keybd_event([byte]$vk, 0, 0, [UIntPtr]::Zero); Start-Sleep -Milliseconds 40; [OdhWin]::keybd_event([byte]$vk, 0, 2, [UIntPtr]::Zero) }
$t0 = Get-Date; $times = @()
for ($i = 0; $i -lt $Frames; $i++) {
    $bmp = New-Object Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
    $g = [Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc(); [OdhWin]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc)
    $gs.DrawImage($bmp, (New-Object Drawing.Rectangle ($i * $CropW), 0, $CropW, $CropH), (New-Object Drawing.Rectangle $CropX, $CropY, $CropW, $CropH), 'Pixel')
    $times += [int]((Get-Date) - $t0).TotalMilliseconds; $g.Dispose(); $bmp.Dispose(); Start-Sleep -Milliseconds 30
}
$strip.Save($OutFile); "frames at ms: $($times -join ' ')"
