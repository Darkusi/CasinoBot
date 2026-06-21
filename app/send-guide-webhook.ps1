param(
    [string]$WebhookUrl = ""
)

$payloadPath = Join-Path $PSScriptRoot "webhook-guide-announcement.json"

if (-not (Test-Path $payloadPath)) {
    Write-Host "Error: webhook-guide-announcement.json not found at $payloadPath" -ForegroundColor Red
    exit 1
}

$body = Get-Content $payloadPath -Raw

if ($WebhookUrl -eq "") {
    Write-Host "Usage: .\send-guide-webhook.ps1 -WebhookUrl ""https://discord.com/api/webhooks/...""" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or pipe to curl manually:" -ForegroundColor Cyan
    Write-Host "  curl -X POST -H ""Content-Type: application/json"" -d @webhook-guide-announcement.json YOUR_WEBHOOK_URL" -ForegroundColor White
    exit 0
}

try {
    $response = Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body $body -ContentType "application/json"
    Write-Host "✓ Guide announcement sent successfully!" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to send: $_" -ForegroundColor Red
}
