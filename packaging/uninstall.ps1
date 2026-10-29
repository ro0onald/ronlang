param([string]$Destination = (Join-Path $env:LOCALAPPDATA 'RonLang\bin'))
$ErrorActionPreference = 'Stop'
$current = [Environment]::GetEnvironmentVariable('Path', 'User')
$entries = @($current -split ';' | Where-Object { $_ -and $_ -ne $Destination })
[Environment]::SetEnvironmentVariable('Path', ($entries -join ';'), 'User')
$executable = Join-Path $Destination 'ron.exe'
if (Test-Path -LiteralPath $executable) { Remove-Item -LiteralPath $executable }
Write-Output 'Removed RonLang executable and its user PATH entry. Project files were preserved.'
