param(
    [string]$Destination = (Join-Path $env:LOCALAPPDATA 'RonLang\bin'),
    [switch]$NoPath
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'ron.exe'
if (-not (Test-Path -LiteralPath $source)) { throw 'ron.exe must be next to install.ps1' }
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
Copy-Item -LiteralPath $source -Destination (Join-Path $Destination 'ron.exe')
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $Destination
}
if (-not $NoPath) {
    $current = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($current -split ';' | Where-Object { $_ })
    if ($entries -notcontains $Destination) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $Destination) -join ';'), 'User')
    }
}
Write-Output "Installed RonLang in $Destination. Open a new terminal and run ron --version."
