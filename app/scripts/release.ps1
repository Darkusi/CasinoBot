param(
  [string]$Version = "2.0.1",
  [string]$Token = "",
  [switch]$DryRun = $false
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path "$root\.."

if (-not $Token) {
  # Try to read from env or git config
  $Token = $env:GH_TOKEN
  if (-not $Token) {
    $Token = (git config --get remote.origin.url 2>$null) -replace '.*:(.*)@.*', '$1'
  }
}

if (-not $Token) {
  Write-Error "GitHub token required. Set GH_TOKEN env var or pass -Token"
  exit 1
}

$exePath = "$projectRoot\build\CasinoBot.exe"
$setupPath = Get-ChildItem "$projectRoot\build\CasinoBot-Setup-$Version.exe" -ErrorAction SilentlyContinue

if (-not (Test-Path $exePath)) {
  Write-Error "CasinoBot.exe not found. Run scripts\build.ps1 first."
  exit 1
}

$repo = "glowrius/casino-bonus-monitor"
$api = "https://api.github.com/repos/$repo/releases"
$headers = @{ Authorization = "token $Token"; Accept = "application/vnd.github.v3+json" }

Write-Output ""
Write-Output "═══════════════════════════════════════"
Write-Output "  Releasing v$Version to GitHub"
Write-Output "═══════════════════════════════════════"

# Tag commit
if (-not $DryRun) {
  Write-Output "  Tagging v$Version..."
  git -C $projectRoot tag "v$Version" -m "Release v$Version"
  git -C $projectRoot push origin "v$Version"
}

# Create release
Write-Output "  Creating GitHub release..."
$body = @{
  tag_name = "v$Version"
  name = "v$Version"
  body = "Casino Bonus Monitor v$Version`r`n---`r`n`r`nSee the [website]($(Get-Content "$projectRoot\docs\index.html" -Raw | Select-String -Pattern 'v[0-9]+\.[0-9]+\.[0-9]+' | ForEach-Object { $_.Matches.Value })) for details."
  draft = $false
  prerelease = $false
} | ConvertTo-Json

if ($DryRun) {
  Write-Output "  [DRY RUN] Would create release with body: $body"
} else {
  $release = Invoke-RestMethod -Uri $api -Method POST -Headers $headers -Body $body -ContentType "application/json"
  $releaseId = $release.id
  $uploadUrl = $release.upload_url -replace '\{.*\}', ''

  Write-Output "  Release created: $($release.html_url)"

  # Upload CasinoBot.exe
  Write-Output "  Uploading CasinoBot.exe..."
  $exeHeaders = @{ Authorization = "token $Token"; "Content-Type" = "application/octet-stream" }
  Invoke-RestMethod -Uri "$uploadUrl?name=CasinoBot.exe" -Method POST -Headers $exeHeaders -InFile $exePath -ErrorAction Stop | Out-Null

  # Upload installer if exists
  if ($setupPath) {
    Write-Output "  Uploading $($setupPath.Name)..."
    Invoke-RestMethod -Uri "$uploadUrl?name=$($setupPath.Name)" -Method POST -Headers $exeHeaders -InFile $setupPath.FullName -ErrorAction Stop | Out-Null
  }

  Write-Output ""
  Write-Output "═══════════════════════════════════════"
  Write-Output "  ✅ Released v$Version"
  Write-Output "  $($release.html_url)"
  Write-Output "═══════════════════════════════════════"
}
