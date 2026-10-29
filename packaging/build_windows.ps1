param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & $Python -m PyInstaller --noconfirm --onefile --name ron --paths . ron.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
    Copy-Item -LiteralPath packaging\install.ps1,packaging\install.cmd,packaging\uninstall.ps1 -Destination dist
    Write-Output 'Built dist/ron.exe. Run packaging/build_installer.ps1 to package the installer.'
} finally { Pop-Location }
