$all = Get-CimInstance Win32_Process
$wv = $all | Where-Object Name -eq 'msedgewebview2.exe'
"msedgewebview2 processes: $($wv.Count)"
foreach ($p in ($wv | Where-Object { $_.CommandLine -notmatch '--type=' })) {
  $par = $all | Where-Object ProcessId -eq $p.ParentProcessId
  $udd = if ($p.CommandLine -match '--user-data-dir="?([^"]+)') { $Matches[1] } else { '?' }
  "browser pid=$($p.ProcessId) parent=$($p.ParentProcessId) ($($par.Name)) udd=$udd"
}
