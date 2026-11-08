# PyNGINX

An educational, Python-only reverse proxy and load balancer inspired by NGINX, built from raw TCP sockets and `asyncio`, with HTTPS/TLS termination support.

## Overview

PyNGINX is designed to demonstrate low-level systems programming concepts in Python:
- Asynchronous networking with `asyncio` and TCP sockets
- TLS termination with `ssl.SSLContext`
- HTTP/1.1 message parsing, framing, and serialization
- Reverse proxying and hop-by-hop header handling
- Load-balancing algorithms (Round Robin, Weighted Round Robin, Least Connections)
- Health checks, failover, backpressure, and timeouts

## Project Status

- **Phase 0 (Repository Bootstrap)**: In progress / Completed
- Target protocol: HTTP/1.1 over TLS (HTTPS)

## Quick Start

### 1. Prerequisites
- Python 3.12+ (tested with Python 3.14)
- OpenSSL (for generating self-signed TLS certificates)
- Git

### 2. Setup Virtual Environment

#### Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

#### Linux / macOS:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Generate Local TLS Certificate
```bash
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/server.key \
  -out certs/server.crt \
  -days 365 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

### 4. Run Tests
```bash
pytest
```

## License
MIT License.
