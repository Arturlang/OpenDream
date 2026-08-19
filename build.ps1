# Fast iteration build for OpenDream. See docs/fast-builds.md.
#
# Frees build locks first: MSBuild's output-copy step retries for ~10s per file
# held by a running client/server, which dominated rebuild times.
#
#   ./build.ps1                  build client + server
#   ./build.ps1 -Target client   build only the client
#   ./build.ps1 -KeepServer      leave running servers alone (client-only locks freed)
#   ./build.ps1 -Full            restore + Robust analyzers (use before committing)
param(
    [ValidateSet('client', 'server', 'both')]
    [string]$Target = 'both',
    [switch]$KeepServer,
    [switch]$Full
)

$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if ($Target -ne 'server') {
        Get-Process OpenDreamClient -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    if ($Target -ne 'client' -and -not $KeepServer) {
        Get-Process OpenDreamServer -ErrorAction SilentlyContinue | Stop-Process -Force
    }
    elseif ($Target -ne 'client' -and (Get-Process OpenDreamServer -ErrorAction SilentlyContinue)) {
        Write-Host "warning: building the server with -KeepServer while one is running will fail on file locks" -ForegroundColor Yellow
    }

    $flags = @('-c', 'Tools', '--nologo')
    if (-not $Full) {
        # Analyzers catch real bugs ([Dependency] misuse etc.) but cost a large slice
        # of compile time; run them via -Full before committing.
        $flags += @('--no-restore', '-p:RunAnalyzers=false')
    }

    $projects = switch ($Target) {
        'client' { @('OpenDreamClient') }
        'server' { @('OpenDreamServer') }
        'both'   { @('OpenDreamServer', 'OpenDreamClient') }
    }

    foreach ($project in $projects) {
        Write-Host ">> dotnet build $project $($flags -join ' ')" -ForegroundColor Cyan
        dotnet build $project @flags
        if ($LASTEXITCODE -ne 0) {
            Write-Host "BUILD FAILED: $project" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }

    Write-Host "OK: $($projects -join ', ')" -ForegroundColor Green
}
finally {
    Pop-Location
}
