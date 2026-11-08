# Certificates Directory

This directory holds TLS certificates and private keys used for local development and testing.

## Security Notice

> **Important**: Never commit private keys (`*.key`), certificate files (`*.crt`, `*.pem`), or certificate signing requests (`*.csr`) to version control. They are strictly ignored by `.gitignore`.

## Generating Local Development Certificates

To generate a self-signed certificate and RSA private key for local development:

### Linux / macOS / Git Bash
```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/server.key \
  -out certs/server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

### Windows PowerShell
```powershell
openssl req -x509 -newkey rsa:2048 -nodes `
  -keyout certs/server.key `
  -out certs/server.crt `
  -days 365 `
  -subj "/CN=localhost" `
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```
