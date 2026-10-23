$ds = Get-Process -Id 47192
$g = Get-CimInstance Win32_Process -Filter "ParentProcessId=47192"
"dreamseeker started $($ds.StartTime.ToString('HH:mm:ss'))"
foreach ($p in $g) { "child $($p.Name) pid=$($p.ProcessId) started $($p.CreationDate.ToString('HH:mm:ss')) cmd=$($p.CommandLine)" }
$wv = Get-CimInstance Win32_Process -Filter "Name='msedgewebview2.exe'" | Where-Object { $_.CommandLine -notmatch '--type=' -and $_.CommandLine -like '*BYOND*cache*WebView2*' }
"webview root: $($wv.ProcessId)"
