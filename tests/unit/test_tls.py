"""Unit tests for TLS context creation and validation."""

import ssl
from pathlib import Path

import pytest

from pynginx.errors import TLSError
from pynginx.network.tls import create_server_ssl_context

CERTS_DIR = Path(__file__).resolve().parent.parent.parent / "certs"
CERT_FILE = CERTS_DIR / "server.crt"
KEY_FILE = CERTS_DIR / "server.key"


def test_create_server_ssl_context_success():
    """Test successful SSLContext creation with valid dev certs."""
    ctx = create_server_ssl_context(CERT_FILE, KEY_FILE)
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


def test_create_server_ssl_context_missing_cert(tmp_path: Path):
    """Test TLSError raised when certificate file is missing."""
    missing_cert = tmp_path / "nonexistent.crt"
    with pytest.raises(TLSError, match="certificate file not found"):
        create_server_ssl_context(missing_cert, KEY_FILE)


def test_create_server_ssl_context_missing_key(tmp_path: Path):
    """Test TLSError raised when private key file is missing."""
    missing_key = tmp_path / "nonexistent.key"
    with pytest.raises(TLSError, match="private key file not found"):
        create_server_ssl_context(CERT_FILE, missing_key)
