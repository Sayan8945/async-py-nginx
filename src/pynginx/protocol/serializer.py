"""HTTP response serializer for PyNGINX."""

import http
import json
from typing import Any

from pynginx.protocol.http_models import HTTPResponse

STANDARD_REASONS: dict[int, str] = {
    code.value: code.phrase for code in http.HTTPStatus
}


class HTTPResponseSerializer:
    """Serializes HTTPResponse instances into wire-formatted HTTP/1.1 bytes."""

    @staticmethod
    def serialize(response: HTTPResponse, default_connection_close: bool = True) -> bytes:
        """Serializes an HTTPResponse into bytes according to RFC 9112.
        
        Args:
            response: HTTPResponse instance.
            default_connection_close: Whether to enforce 'Connection: close' (default for Phase 1).
            
        Returns:
            Wire-ready bytes sequence.
        """
        reason = response.reason_phrase or STANDARD_REASONS.get(
            response.status_code, "Unknown Status"
        )
        status_line = f"{response.version} {response.status_code} {reason}\r\n"

        # Normalize headers to preserve custom casing while ensuring required headers exist
        headers: dict[str, str] = {}
        for k, v in response.headers.items():
            headers[k] = str(v)

        # Check for case-insensitive presence of Content-Length
        has_content_length = any(k.lower() == "content-length" for k in headers)
        if not has_content_length:
            headers["Content-Length"] = str(len(response.body))

        # Check for Connection header
        has_connection = any(k.lower() == "connection" for k in headers)
        if not has_connection and default_connection_close:
            headers["Connection"] = "close"

        header_lines = [status_line]
        for name, value in headers.items():
            header_lines.append(f"{name}: {value}\r\n")
        header_lines.append("\r\n")

        head_bytes = "".join(header_lines).encode("latin-1")
        return head_bytes + response.body

    @classmethod
    def create_json_response(
        cls,
        status_code: int,
        data: Any,
        headers: dict[str, str] | None = None,
        reason_phrase: str = "",
    ) -> HTTPResponse:
        """Helper to create a standard JSON HTTPResponse."""
        body_bytes = json.dumps(data, indent=2).encode("utf-8")
        resp_headers = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            resp_headers.update(headers)
        return HTTPResponse(
            status_code=status_code,
            headers=resp_headers,
            body=body_bytes,
            reason_phrase=reason_phrase,
        )

    @classmethod
    def create_error_response(
        cls,
        status_code: int,
        message: str,
        reason_phrase: str = "",
    ) -> HTTPResponse:
        """Helper to create a standard error JSON response."""
        data = {
            "error": {
                "status": status_code,
                "message": message,
            }
        }
        return cls.create_json_response(
            status_code=status_code,
            data=data,
            reason_phrase=reason_phrase,
        )
