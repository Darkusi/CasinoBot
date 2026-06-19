param()

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path "$root\.."

Write-Output ""
Write-Output "═══════════════════════════════════════"
Write-Output "  Building Claim City Dashboard"
Write-Output "═══════════════════════════════════════"

if (-not (Test-Path "$projectRoot\build")) {
  New-Item -ItemType Directory -Path "$projectRoot\build" -Force | Out-Null
}

# Install deps
pip install customtkinter requests pyinstaller 2>&1 | Out-Null

# Build EXE
pyinstaller --onefile --windowed --name CasinoDashboard --distpath "$projectRoot\build" "$projectRoot\src\ui\main.py" 2>&1

if ($LASTEXITCODE -eq 0) {
  $size = (Get-Item "$projectRoot\build\CasinoDashboard.exe").Length / 1MB
  Write-Output "  Dashboard built: CasinoDashboard.exe"
  Write-Output "  Size: $([math]::Round($size,1)) MB"
} else {
  Write-Error "PyInstaller build failed"
  exit 1
}
