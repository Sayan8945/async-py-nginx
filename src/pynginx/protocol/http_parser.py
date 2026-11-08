"""HTTP/1.1 message parser with strict RFC 9112 compliance and security limits."""

import asyncio
import re

from pynginx.errors import (
    BadRequestError,
    ClientDisconnectedError,
    HTTPVersionNotSupportedError,
    NotImplementedHTTPError,
    PayloadTooLargeError,
    RequestTimeoutError,
    UriTooLongError,
)
from pynginx.protocol.http_models import HTTPRequest

# RFC 9110 Section 5.6.2 token character pattern
TOKEN_REGEX = re.compile(r"^[!#$%&'*+\-.^_`|~0-9a-zA-Z]+$")
# HTTP version pattern
HTTP_VERSION_REGEX = re.compile(r"^HTTP/(\d+)\.(\d+)$")


class HTTPParser:
    """Parser for HTTP/1.1 requests enforcing strict bounds and protocol invariants."""

    DEFAULT_MAX_REQUEST_LINE_BYTES = 8192      # 8 KB
    DEFAULT_MAX_HEADER_BYTES = 65536           # 64 KB
    DEFAULT_MAX_BODY_BYTES = 1048576           # 1 MB
    CHUNK_READ_SIZE = 8192                     # 8 KB read buffer

    def __init__(
        self,
        max_request_line_bytes: int = DEFAULT_MAX_REQUEST_LINE_BYTES,
        max_header_bytes: int = DEFAULT_MAX_HEADER_BYTES,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        request_timeout: float = 15.0,
    ) -> None:
        self.max_request_line_bytes = max_request_line_bytes
        self.max_header_bytes = max_header_bytes
        self.max_body_bytes = max_body_bytes
        self.request_timeout = request_timeout

    @classmethod
    def parse_request_line(
        cls, line: str, max_uri_length: int = DEFAULT_MAX_REQUEST_LINE_BYTES
    ) -> tuple[str, str, str]:
        """Parses and validates the HTTP request line (RFC 9112 Section 3).
        
        Format: method SP request-target SP HTTP-version
        """
        # A request line must not contain control characters
        for ch in line:
            if ord(ch) < 32 or ord(ch) == 127:
                raise BadRequestError("Control character in request line")

        parts = line.split(" ")
        if len(parts) != 3:
            raise BadRequestError(
                f"Malformed request line (expected 3 tokens, got {len(parts)})"
            )

        method, target, version = parts

        if not method or not TOKEN_REGEX.match(method):
            raise BadRequestError(f"Invalid HTTP method token: {method!r}")

        if not target:
            raise BadRequestError("Empty request target")

        if len(target.encode("utf-8")) > max_uri_length:
            raise UriTooLongError("Request target URI too long")

        version_match = HTTP_VERSION_REGEX.match(version)
        if not version_match:
            raise BadRequestError(f"Malformed HTTP version: {version!r}")

        major, minor = int(version_match.group(1)), int(version_match.group(2))
        if major > 1:
            raise HTTPVersionNotSupportedError(
                f"HTTP/{major}.{minor} is not supported; only HTTP/1.1 is supported"
            )
        if major != 1 or minor != 1:
            # We strictly enforce HTTP/1.1 for Phase 1
            raise HTTPVersionNotSupportedError(
                f"Unsupported HTTP version {version}; HTTP/1.1 required"
            )

        return method, target, version

    @classmethod
    def parse_headers(cls, raw_headers: list[str]) -> dict[str, str]:
        """Parses and validates HTTP headers according to RFC 9112 Section 5.
        
        Returns case-folded (lowercase key) dictionary of headers.
        """
        headers: dict[str, str] = {}
        content_length_values: list[str] = []
        host_count = 0

        for line in raw_headers:
            if not line:
                continue

            # RFC 9112 Section 5.2: Obsolete line folding is forbidden
            if line.startswith((" ", "\t")):
                raise BadRequestError("Obsolete line folding is not permitted")

            colon_pos = line.find(":")
            if colon_pos == -1:
                raise BadRequestError(f"Header missing colon separator: {line!r}")

            # RFC 9112 Section 5.1: No whitespace allowed between field name and colon
            if colon_pos > 0 and line[colon_pos - 1] in (" ", "\t"):
                raise BadRequestError(
                    "Whitespace not permitted between header field name and colon"
                )

            name = line[:colon_pos]
            value = line[colon_pos + 1:].strip(" \t")

            if not TOKEN_REGEX.match(name):
                raise BadRequestError(f"Invalid header field name: {name!r}")

            # Reject control characters in header value (except horizontal tab 0x09)
            for ch in value:
                if (ord(ch) < 32 and ch != "\t") or ord(ch) == 127:
                    raise BadRequestError(f"Invalid control character in header value for {name!r}")

            name_lower = name.lower()

            if name_lower == "host":
                host_count += 1
                if host_count > 1:
                    raise BadRequestError("Multiple Host headers are not permitted")
                headers[name_lower] = value
            elif name_lower == "content-length":
                content_length_values.append(value)
            elif name_lower == "transfer-encoding":
                # Save Transfer-Encoding for semantic validation
                headers[name_lower] = value
            else:
                if name_lower in headers:
                    # RFC 9110 Section 5.3: Combine multiple field lines with comma
                    headers[name_lower] = f"{headers[name_lower]}, {value}"
                else:
                    headers[name_lower] = value

        # RFC 9112 Section 3.2: Host header is mandatory in HTTP/1.1
        if host_count == 0 or not headers.get("host"):
            raise BadRequestError("Missing required Host header for HTTP/1.1")

        # RFC 9112 Section 6.1: Transfer-Encoding combined with Content-Length is rejected
        has_te = "transfer-encoding" in headers
        has_cl = len(content_length_values) > 0

        if has_te and has_cl:
            raise BadRequestError(
                "Conflicting message framing: both Transfer-Encoding and Content-Length present"
            )

        if has_te:
            # Phase 1 explicitly rejects Transfer-Encoding
            raise NotImplementedHTTPError(
                "Transfer-Encoding is not supported in Phase 1"
            )

        # Content-Length validation
        if has_cl:
            normalized_lengths: list[int] = []
            for raw_val in content_length_values:
                # Value may be comma-separated list of identical integers (RFC 9110 Section 8.6)
                parts = [p.strip() for p in raw_val.split(",")]
                for p in parts:
                    if not p.isdigit():
                        raise BadRequestError(f"Invalid non-integer Content-Length: {p!r}")
                    normalized_lengths.append(int(p))

            # All Content-Length values must be identical
            first_len = normalized_lengths[0]
            if any(l != first_len for l in normalized_lengths):
                raise BadRequestError("Conflicting Content-Length header values")

            headers["content-length"] = str(first_len)

        return headers

    async def read_request(self, reader: asyncio.StreamReader) -> HTTPRequest:
        """Reads and parses a full HTTP request from an asyncio StreamReader."""
        try:
            return await asyncio.wait_for(
                self._read_request_internal(reader),
                timeout=self.request_timeout,
            )
        except TimeoutError:
            raise RequestTimeoutError("Timeout reading HTTP request")

    async def _read_request_internal(self, reader: asyncio.StreamReader) -> HTTPRequest:
        head_buffer = bytearray()
        separator_idx = -1
        sep_len = 4  # for \r\n\r\n

        max_head_limit = self.max_request_line_bytes + self.max_header_bytes

        # Read head incrementally until \r\n\r\n (or \n\n)
        while True:
            # Check for \r\n\r\n
            separator_idx = head_buffer.find(b"\r\n\r\n")
            if separator_idx != -1:
                sep_len = 4
                break

            # Also check for \n\n as relaxed delimiter
            separator_idx = head_buffer.find(b"\n\n")
            if separator_idx != -1:
                sep_len = 2
                break

            if len(head_buffer) > max_head_limit:
                raise PayloadTooLargeError("Request header section exceeds size limit")

            chunk = await reader.read(self.CHUNK_READ_SIZE)
            if not chunk:
                if len(head_buffer) == 0:
                    raise ClientDisconnectedError("Client disconnected before sending data")
                raise BadRequestError("Unexpected EOF while reading request headers")

            head_buffer.extend(chunk)

        raw_head = bytes(head_buffer[:separator_idx])
        body_prefix = bytes(head_buffer[separator_idx + sep_len:])

        try:
            head_str = raw_head.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise BadRequestError("Non-decodable header bytes") from exc

        # Split into lines
        lines = [line.rstrip("\r") for line in head_str.split("\n")]
        if not lines or not lines[0]:
            raise BadRequestError("Empty request line")

        request_line = lines[0]
        request_line_bytes_len = len(request_line.encode("latin-1"))
        if request_line_bytes_len > self.max_request_line_bytes:
            raise PayloadTooLargeError("Request line exceeds maximum allowed size")

        method, target, version = self.parse_request_line(
            request_line, max_uri_length=self.max_request_line_bytes
        )

        header_section_bytes_len = len(raw_head) - request_line_bytes_len
        if header_section_bytes_len > self.max_header_bytes:
            raise PayloadTooLargeError("Request header section exceeds size limit")

        header_lines = lines[1:]
        headers = self.parse_headers(header_lines)

        # Parse body if Content-Length specified
        body = b""
        if "content-length" in headers:
            content_length = int(headers["content-length"])
            if content_length > self.max_body_bytes:
                raise PayloadTooLargeError(
                    f"Content-Length {content_length} exceeds limit of {self.max_body_bytes} bytes"
                )

            body = await self._read_fixed_body(reader, content_length, body_prefix)

        return HTTPRequest(
            method=method,
            target=target,
            version=version,
            headers=headers,
            body=body,
        )

    async def _read_fixed_body(
        self, reader: asyncio.StreamReader, content_length: int, prefix: bytes
    ) -> bytes:
        """Reads exactly content_length bytes without unbounded memory pre-allocation."""
        body = bytearray(prefix[:content_length])
        remaining = content_length - len(body)

        while remaining > 0:
            to_read = min(remaining, self.CHUNK_READ_SIZE)
            chunk = await reader.read(to_read)
            if not chunk:
                raise BadRequestError(
                    f"Unexpected EOF reading body (expected {content_length} bytes, received {len(body)})"
                )
            body.extend(chunk)
            remaining -= len(chunk)

        return bytes(body)
