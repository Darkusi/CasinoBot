param(
  [string]$Version = "2.0.0"
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path "$root\.."

# Find ISCC.exe from common install locations
$isccPaths = @(
  "C:\Users\GLOW\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
  "C:\Program Files\Inno Setup 6\ISCC.exe",
  "${env:ChocolateyInstall}\lib\innosetup\tools\ISCC.exe",
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $null
foreach ($p in $isccPaths) {
  if (Test-Path $p) { $iscc = $p; break }
}

if (-not $iscc) {
  Write-Error "ISCC.exe not found. Install Inno Setup 6 first."
  exit 1
}

# Try dist/ first, then build/
$exePath = "$projectRoot\dist\CasinoBot.exe"
if (-not (Test-Path $exePath)) {
  $exePath = "$projectRoot\build\CasinoBot.exe"
}
if (-not (Test-Path $exePath)) {
  Write-Error "CasinoBot.exe not found. Run PyInstaller build first."
  exit 1
}
# Copy exe into build/ for Inno Setup
Copy-Item -Path $exePath -Destination "$projectRoot\build\CasinoBot.exe" -Force

if (-not (Test-Path "$projectRoot\build")) {
  New-Item -ItemType Directory -Path "$projectRoot\build" -Force | Out-Null
}

Write-Output ""
Write-Output "═══════════════════════════════════════"
Write-Output "  Building Installer v$Version"
Write-Output "═══════════════════════════════════════"
Write-Output ""

Set-Location $root

# Update version in .iss
(Get-Content "setup.iss") -replace '#define MyAppVersion ".*"', "#define MyAppVersion `"$Version`"" | Set-Content "setup.iss"

# Compile
& $iscc "setup.iss" /Q 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Error "Inno Setup compilation failed (exit: $LASTEXITCODE)"
  exit 1
}

$installer = Get-ChildItem "$projectRoot\build\CasinoBot-Setup-$Version.exe"
if ($installer) {
  $size = $installer.Length / 1MB
  Write-Output ""
  Write-Output "═══════════════════════════════════════"
  Write-Output "  Installer built: $($installer.Name)"
  Write-Output "  Size: $([math]::Round($size,1)) MB"
  Write-Output "═══════════════════════════════════════"
} else {
  Write-Error "Installer not found after compilation"
  exit 1
}
