$expiry = (Get-Date).AddYears(10)
$cert = New-SelfSignedCertificate -Type Custom -Subject "CN=Casino Bonus Monitor" -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3","2.5.29.19={text}") -KeyUsage DigitalSignature -FriendlyName "Casino Bonus Monitor" -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter $expiry
Write-Output "Certificate created: $($cert.Thumbprint)"

$pwd = ConvertTo-SecureString -String "casino123" -Force -AsPlainText
$certPath = Join-Path $PSScriptRoot "CasinoBot.pfx"
Export-PfxCertificate -Cert $cert -FilePath $certPath -Password $pwd
Write-Output "Exported to: $certPath"
