param([string]$ExePath)

$cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Thumbprint -eq "7A0B4A09E7A54F0A78551628C1FFB3ED95DABDFF" } | Select-Object -First 1
if (-not $cert) {
  Write-Error "Code signing certificate not found"
  exit 1
}

Write-Output "Signing: $ExePath"
Write-Output "  Using cert: $($cert.Subject) (thumbprint: $($cert.Thumbprint))"
Set-AuthenticodeSignature -FilePath $ExePath -Certificate $cert -TimestampServer "http://timestamp.digicert.com"

$sig = Get-AuthenticodeSignature $ExePath
if ($sig.Status -eq "Valid") {
  Write-Output "  Signature status: Valid"
} else {
  Write-Output "  Signature status: $($sig.Status)"
}
