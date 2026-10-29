param([string]$ReleaseDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) 'dist'))
$ErrorActionPreference = 'Stop'
$release = (Resolve-Path -LiteralPath $ReleaseDirectory).Path
foreach ($name in @('ron.exe','install.ps1','install.cmd','uninstall.ps1')) {
    if (-not (Test-Path -LiteralPath (Join-Path $release $name))) { throw "Missing $name" }
}
$setup = Join-Path $release 'RonLang-1.0.0rc1-setup.exe'
$sed = Join-Path $release 'installer.sed'
$contents = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=Install RonLang for your Windows user account?
DisplayLicense=
FinishMessage=RonLang installed. Open a new terminal and run ron --version.
TargetName=$setup
FriendlyName=RonLang 1.0 release candidate
AppLaunched=cmd.exe /c install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=cmd.exe /c install.cmd
UserQuietInstCmd=cmd.exe /c install.cmd
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$release\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
[Strings]
FILE0="ron.exe"
FILE1="install.ps1"
FILE2="install.cmd"
FILE3="uninstall.ps1"
"@
Set-Content -LiteralPath $sed -Value $contents -Encoding ascii
$process = Start-Process -FilePath "$env:WINDIR\System32\iexpress.exe" -ArgumentList '/N /Q /M installer.sed' -WorkingDirectory $release -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $setup)) { throw 'Installer packaging failed' }
Write-Output $setup
