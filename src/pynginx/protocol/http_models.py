"""HTTP models for PyNGINX."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class HTTPRequest:
    """Represents a parsed HTTP request.
    
    Attributes:
        method: HTTP method in upper-case (e.g. GET, POST).
        target: Request URI target (e.g. /index.html, /api/v1?user=1).
        version: HTTP protocol version string (e.g. HTTP/1.1).
        headers: Case-folded (lowercased key) dictionary of headers.
        body: Raw request body as bytes.
    """

    method: str
    target: str
    version: str
    headers: dict[str, str]
    body: bytes = b""


@dataclass(slots=True)
class HTTPResponse:
    """Represents an HTTP response to be serialized.
    
    Attributes:
        status_code: Three-digit HTTP status code (e.g. 200, 400).
        headers: Response headers mapping.
        body: Response body bytes.
        version: HTTP version string (defaults to HTTP/1.1).
        reason_phrase: Optional reason phrase (e.g. OK, Bad Request).
    """

    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    version: str = "HTTP/1.1"
    reason_phrase: str = ""
