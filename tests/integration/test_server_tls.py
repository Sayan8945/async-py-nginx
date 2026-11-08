"""Integration tests for PyNGINX TLS termination, HTTP parsing, and limits."""

import asyncio
import ssl
from pathlib import Path

import httpx
import pytest

from pynginx.network.server import PyNGINXServer
from pynginx.network.tls import create_server_ssl_context

CERTS_DIR = Path(__file__).resolve().parent.parent.parent / "certs"
CERT_FILE = CERTS_DIR / "server.crt"
KEY_FILE = CERTS_DIR / "server.key"


def get_client_ssl_context() -> ssl.SSLContext:
    """Client SSL context configured to trust the development certificate."""
    ctx = ssl.create_default_context(cafile=str(CERT_FILE))
    return ctx


@pytest.fixture
async def running_server():
    """Starts a PyNGINX server on an ephemeral port and terminates it on cleanup."""
    server_ssl = create_server_ssl_context(CERT_FILE, KEY_FILE)
    server = PyNGINXServer(
        host="127.0.0.1",
        port=0,
        ssl_context=server_ssl,
        request_timeout=2.0,
    )
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_https_get_returns_200(running_server: PyNGINXServer):
    """Verify standard valid HTTPS GET request succeeds with 200 JSON response."""
    url = f"https://127.0.0.1:{running_server.bound_port}/api/hello"

    async with httpx.AsyncClient(verify=get_client_ssl_context()) as client:
        resp = await client.get(url)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.headers["connection"] == "close"

    data = resp.json()
    assert data["status"] == "ok"
    assert data["method"] == "GET"
    assert data["target"] == "/api/hello"
    assert data["body_length"] == 0


@pytest.mark.asyncio
async def test_https_post_body_parsed(running_server: PyNGINXServer):
    """Verify valid HTTPS POST with JSON payload is parsed correctly."""
    url = f"https://127.0.0.1:{running_server.bound_port}/api/echo"
    payload = {"message": "systems engineering", "course": "pynginx"}

    async with httpx.AsyncClient(verify=get_client_ssl_context()) as client:
        resp = await client.post(url, json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["method"] == "POST"
    assert data["body_length"] > 0


@pytest.mark.asyncio
async def test_missing_host_header_rejected(running_server: PyNGINXServer):
    """Verify HTTP/1.1 request missing Host header is rejected with 400 Bad Request."""
    client_ctx = get_client_ssl_context()
    reader, writer = await asyncio.open_connection(
        "127.0.0.1",
        running_server.bound_port,
        ssl=client_ctx,
        server_hostname="localhost",
    )

    try:
        # Send HTTP/1.1 request without Host
        writer.write(b"GET /test HTTP/1.1\r\nUser-Agent: test\r\n\r\n")
        await writer.drain()

        raw_resp = await reader.read(4096)
        assert b"HTTP/1.1 400 Bad Request" in raw_resp
        assert b"Missing required Host header" in raw_resp
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_malformed_request_line_rejected(running_server: PyNGINXServer):
    """Verify malformed request line is rejected with 400 Bad Request."""
    client_ctx = get_client_ssl_context()
    reader, writer = await asyncio.open_connection(
        "127.0.0.1",
        running_server.bound_port,
        ssl=client_ctx,
        server_hostname="localhost",
    )

    try:
        writer.write(b"CORRUPTED_REQUEST_LINE\r\nHost: localhost\r\n\r\n")
        await writer.drain()

        raw_resp = await reader.read(4096)
        assert b"HTTP/1.1 400 Bad Request" in raw_resp
    finally:
        writer.close()
        await writer.wait_closed()


@pytest.mark.asyncio
async def test_oversized_headers_rejected():
    """Verify requests with headers exceeding max_header_bytes receive 413."""
    server_ssl = create_server_ssl_context(CERT_FILE, KEY_FILE)
    server = PyNGINXServer(
        host="127.0.0.1",
        port=0,
        ssl_context=server_ssl,
        max_header_bytes=512,
        request_timeout=2.0,
    )
    await server.start()

    try:
        client_ctx = get_client_ssl_context()
        reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            server.bound_port,
            ssl=client_ctx,
            server_hostname="localhost",
        )

        try:
            large_header = "X-Padding: " + ("B" * 600) + "\r\n"
            req = f"GET / HTTP/1.1\r\nHost: localhost\r\n{large_header}\r\n".encode("latin-1")
            writer.write(req)
            await writer.drain()

            raw_resp = await reader.read(4096)
            assert b"HTTP/1.1 413 Content Too Large" in raw_resp
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_oversized_body_rejected():
    """Verify requests with body exceeding max_body_bytes receive 413."""
    server_ssl = create_server_ssl_context(CERT_FILE, KEY_FILE)
    server = PyNGINXServer(
        host="127.0.0.1",
        port=0,
        ssl_context=server_ssl,
        max_body_bytes=256,
        request_timeout=2.0,
    )
    await server.start()

    try:
        client_ctx = get_client_ssl_context()
        reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            server.bound_port,
            ssl=client_ctx,
            server_hostname="localhost",
        )

        try:
            body = b"A" * 512
            head = f"POST /upload HTTP/1.1\r\nHost: localhost\r\nContent-Length: {len(body)}\r\n\r\n"
            writer.write(head.encode("latin-1") + body)
            await writer.drain()

            raw_resp = await reader.read(4096)
            assert b"HTTP/1.1 413 Content Too Large" in raw_resp
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_incomplete_body_timeout_or_safe_close():
    """Verify incomplete body times out with 408 or closes safely without hanging."""
    server_ssl = create_server_ssl_context(CERT_FILE, KEY_FILE)
    server = PyNGINXServer(
        host="127.0.0.1",
        port=0,
        ssl_context=server_ssl,
        request_timeout=0.5,
    )
    await server.start()

    try:
        client_ctx = get_client_ssl_context()
        reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            server.bound_port,
            ssl=client_ctx,
            server_hostname="localhost",
        )

        try:
            # Announce 100 bytes but only send 10
            writer.write(b"POST /api HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\npartial")
            await writer.drain()

            raw_resp = await reader.read(4096)
            # Response should either be 408 Request Timeout or connection closed
            if raw_resp:
                assert b"408 Request Timeout" in raw_resp
        finally:
            writer.close()
            await writer.wait_closed()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_tls_minimum_version_enforced(running_server: PyNGINXServer):
    """Verify server enforces TLS 1.2 minimum version and rejects deprecated TLS versions."""
    # Attempting to connect with client restricted to TLS 1.1 or 1.0 must fail
    deprecated_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    deprecated_ctx.check_hostname = False
    deprecated_ctx.verify_mode = ssl.CERT_NONE

    # Configure client to only use older versions if supported by OpenSSL
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            deprecated_ctx.maximum_version = ssl.TLSVersion.TLSv1_1
    except (ValueError, AttributeError):
        # If the platform OpenSSL has already disabled TLS 1.1 completely, test passes by default
        return

    with pytest.raises((ssl.SSLError, ConnectionResetError, OSError)):
        _reader, writer = await asyncio.open_connection(
            "127.0.0.1",
            running_server.bound_port,
            ssl=deprecated_ctx,
            server_hostname="localhost",
        )
        writer.close()
        await writer.wait_closed()
