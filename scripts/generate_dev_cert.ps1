# PowerShell script to generate self-signed dev certificate for PyNGINX

$certsDir = Join-Path $PSScriptRoot "..\certs"
if (-not (Test-Path $certsDir)) {
    New-Item -ItemType Directory -Path $certsDir | Out-Null
}

$keyFile = Join-Path $certsDir "server.key"
$crtFile = Join-Path $certsDir "server.crt"

Write-Host "Generating development TLS certificate for localhost..." -ForegroundColor Cyan

openssl req -x509 -newkey rsa:2048 -nodes `
  -keyout $keyFile `
  -out $crtFile `
  -days 365 `
  -subj "/CN=localhost" `
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Certificate and private key generated successfully in $certsDir" -ForegroundColor Green
} else {
    Write-Error "Failed to generate certificate via OpenSSL"
}
