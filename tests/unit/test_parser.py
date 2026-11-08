"""Unit tests for HTTP parser, models, and response serializer."""

import asyncio

import pytest

from pynginx.errors import (
    BadRequestError,
    ClientDisconnectedError,
    HTTPVersionNotSupportedError,
    NotImplementedHTTPError,
    PayloadTooLargeError,
    UriTooLongError,
)
from pynginx.protocol.http_models import HTTPResponse
from pynginx.protocol.http_parser import HTTPParser
from pynginx.protocol.serializer import HTTPResponseSerializer

# ============================================================================
# Request Line Tests
# ============================================================================


def test_parse_request_line_valid():
    """Test standard valid HTTP request lines."""
    method, target, version = HTTPParser.parse_request_line("GET /index.html HTTP/1.1")
    assert method == "GET"
    assert target == "/index.html"
    assert version == "HTTP/1.1"

    method, target, version = HTTPParser.parse_request_line("POST /api/v1/resource?id=123 HTTP/1.1")
    assert method == "POST"
    assert target == "/api/v1/resource?id=123"
    assert version == "HTTP/1.1"


def test_parse_request_line_malformed_tokens():
    """Test rejection of request lines with too few or too many tokens."""
    with pytest.raises(BadRequestError, match="Malformed request line"):
        HTTPParser.parse_request_line("GET /")

    with pytest.raises(BadRequestError, match="Malformed request line"):
        HTTPParser.parse_request_line("GET / HTTP/1.1 EXTRA")


def test_parse_request_line_invalid_method():
    """Test rejection of invalid method tokens."""
    with pytest.raises(BadRequestError, match="Malformed request line"):
        HTTPParser.parse_request_line("GE T / HTTP/1.1")

    with pytest.raises(BadRequestError, match="Invalid HTTP method token"):
        HTTPParser.parse_request_line("GET@BAD / HTTP/1.1")


def test_parse_request_line_control_characters():
    """Test rejection of control characters in request line."""
    with pytest.raises(BadRequestError, match="Control character in request line"):
        HTTPParser.parse_request_line("GET /\x00 HTTP/1.1")


def test_parse_request_line_target_too_long():
    """Test rejection when target URI exceeds configured maximum."""
    long_target = "/" + "a" * 100
    with pytest.raises(UriTooLongError):
        HTTPParser.parse_request_line(f"GET {long_target} HTTP/1.1", max_uri_length=50)


def test_parse_request_line_unsupported_versions():
    """Test rejection of non-HTTP/1.1 versions."""
    with pytest.raises(HTTPVersionNotSupportedError, match="HTTP/2.0 is not supported"):
        HTTPParser.parse_request_line("GET / HTTP/2.0")

    with pytest.raises(HTTPVersionNotSupportedError, match="HTTP/3.0 is not supported"):
        HTTPParser.parse_request_line("GET / HTTP/3.0")

    with pytest.raises(HTTPVersionNotSupportedError, match="Unsupported HTTP version"):
        HTTPParser.parse_request_line("GET / HTTP/1.0")


# ============================================================================
# Header Parsing Tests
# ============================================================================


def test_parse_headers_valid():
    """Test parsing of standard headers and case insensitivity."""
    raw = [
        "Host: localhost:8443",
        "User-Agent: curl/7.68.0",
        "Accept: application/json",
        "X-Custom-Header: value1",
        "X-Custom-Header: value2",
    ]
    headers = HTTPParser.parse_headers(raw)
    assert headers["host"] == "localhost:8443"
    assert headers["user-agent"] == "curl/7.68.0"
    assert headers["accept"] == "application/json"
    assert headers["x-custom-header"] == "value1, value2"


def test_parse_headers_missing_host():
    """Test RFC 9112 Section 3.2 requirement for Host header."""
    raw = [
        "User-Agent: test",
    ]
    with pytest.raises(BadRequestError, match="Missing required Host header"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_multiple_host():
    """Test rejection of multiple Host headers."""
    raw = [
        "Host: localhost",
        "Host: example.com",
    ]
    with pytest.raises(BadRequestError, match="Multiple Host headers are not permitted"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_whitespace_before_colon():
    """Test RFC 9112 Section 5.1 rejection of whitespace before colon."""
    raw = [
        "Host : localhost",
    ]
    with pytest.raises(BadRequestError, match="Whitespace not permitted"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_obsolete_line_folding():
    """Test RFC 9112 Section 5.2 rejection of obsolete line folding."""
    raw = [
        "Host: localhost",
        " folded line",
    ]
    with pytest.raises(BadRequestError, match="Obsolete line folding"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_transfer_encoding_rejected():
    """Test Phase 1 rejection of Transfer-Encoding."""
    raw = [
        "Host: localhost",
        "Transfer-Encoding: chunked",
    ]
    with pytest.raises(NotImplementedHTTPError, match="Transfer-Encoding is not supported in Phase 1"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_te_and_cl_conflict():
    """Test RFC 9112 Section 6.1 rejection of both Transfer-Encoding and Content-Length."""
    raw = [
        "Host: localhost",
        "Content-Length: 10",
        "Transfer-Encoding: chunked",
    ]
    with pytest.raises(BadRequestError, match="Conflicting message framing"):
        HTTPParser.parse_headers(raw)


def test_parse_headers_content_length_validation():
    """Test Content-Length validation rules."""
    # Valid
    headers = HTTPParser.parse_headers(["Host: localhost", "Content-Length: 42"])
    assert headers["content-length"] == "42"

    # Valid identical multiple values
    headers = HTTPParser.parse_headers(["Host: localhost", "Content-Length: 42, 42"])
    assert headers["content-length"] == "42"

    # Conflicting multiple values
    with pytest.raises(BadRequestError, match="Conflicting Content-Length"):
        HTTPParser.parse_headers(["Host: localhost", "Content-Length: 42, 43"])

    # Non-integer value
    with pytest.raises(BadRequestError, match="Invalid non-integer Content-Length"):
        HTTPParser.parse_headers(["Host: localhost", "Content-Length: abc"])

    # Negative integer value
    with pytest.raises(BadRequestError, match="Invalid non-integer Content-Length"):
        HTTPParser.parse_headers(["Host: localhost", "Content-Length: -5"])


# ============================================================================
# Full Stream Parser Tests
# ============================================================================


async def create_stream_reader(data: bytes) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


@pytest.mark.asyncio
async def test_parser_read_get_request():
    raw = b"GET /status HTTP/1.1\r\nHost: localhost\r\nUser-Agent: test\r\n\r\n"
    reader = await create_stream_reader(raw)
    parser = HTTPParser()
    req = await parser.read_request(reader)

    assert req.method == "GET"
    assert req.target == "/status"
    assert req.version == "HTTP/1.1"
    assert req.headers["host"] == "localhost"
    assert req.body == b""


@pytest.mark.asyncio
async def test_parser_read_post_request_with_body():
    payload = b'{"name": "test", "active": true}'
    head = (
        f"POST /api/submit HTTP/1.1\r\n"
        f"Host: localhost\r\n"
        f"Content-Type: application/json\r\n"
        f"Content-Length: {len(payload)}\r\n\r\n"
    ).encode("latin-1")
    raw = head + payload
    reader = await create_stream_reader(raw)
    parser = HTTPParser()
    req = await parser.read_request(reader)

    assert req.method == "POST"
    assert req.target == "/api/submit"
    assert req.headers["content-length"] == str(len(payload))
    assert req.body == payload


@pytest.mark.asyncio
async def test_parser_body_exceeds_max_body_bytes():
    payload = b"X" * 1024
    head = (
        f"POST /upload HTTP/1.1\r\n"
        f"Host: localhost\r\n"
        f"Content-Length: {len(payload)}\r\n\r\n"
    ).encode("latin-1")
    raw = head + payload
    reader = await create_stream_reader(raw)
    parser = HTTPParser(max_body_bytes=512)

    with pytest.raises(PayloadTooLargeError, match="exceeds limit"):
        await parser.read_request(reader)


@pytest.mark.asyncio
async def test_parser_oversized_headers():
    large_header = "X-Large: " + ("a" * 1000) + "\r\n"
    raw = f"GET / HTTP/1.1\r\nHost: localhost\r\n{large_header}\r\n".encode("latin-1")
    reader = await create_stream_reader(raw)
    parser = HTTPParser(max_header_bytes=500)

    with pytest.raises(PayloadTooLargeError, match="Request header section exceeds size limit"):
        await parser.read_request(reader)


@pytest.mark.asyncio
async def test_parser_unexpected_eof_body():
    raw = (
        b"POST /api HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Length: 100\r\n\r\n"
        b"short-body"
    )
    reader = await create_stream_reader(raw)
    parser = HTTPParser()

    with pytest.raises(BadRequestError, match="Unexpected EOF reading body"):
        await parser.read_request(reader)


@pytest.mark.asyncio
async def test_parser_client_disconnect_empty():
    reader = await create_stream_reader(b"")
    parser = HTTPParser()

    with pytest.raises(ClientDisconnectedError):
        await parser.read_request(reader)


# ============================================================================
# Response Serializer Tests
# ============================================================================


def test_serializer_basic_response():
    resp = HTTPResponse(
        status_code=200,
        headers={"Content-Type": "text/plain"},
        body=b"Hello, PyNGINX!",
    )
    serialized = HTTPResponseSerializer.serialize(resp)

    expected_head = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: text/plain\r\n"
        b"Content-Length: 15\r\n"
        b"Connection: close\r\n\r\n"
    )
    assert serialized == expected_head + b"Hello, PyNGINX!"


def test_serializer_json_helper():
    resp = HTTPResponseSerializer.create_json_response(200, {"status": "ok"})
    serialized = HTTPResponseSerializer.serialize(resp)

    assert b"HTTP/1.1 200 OK\r\n" in serialized
    assert b"Content-Type: application/json; charset=utf-8\r\n" in serialized
    assert b"Connection: close\r\n" in serialized
    assert b'"status": "ok"' in serialized


def test_serializer_error_helper():
    resp = HTTPResponseSerializer.create_error_response(400, "Bad Request Syntax")
    serialized = HTTPResponseSerializer.serialize(resp)

    assert b"HTTP/1.1 400 Bad Request\r\n" in serialized
    assert b'"status": 400' in serialized
    assert b'"message": "Bad Request Syntax"' in serialized
