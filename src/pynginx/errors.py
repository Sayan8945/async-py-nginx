"""PyNGINX error and exception hierarchy.

Distinguishes protocol errors, timeouts, disconnects, TLS issues,
and internal server errors without masking them under a broad catch-all.
"""



class PyNGINXError(Exception):
    """Base exception for all PyNGINX errors."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class ClientDisconnectedError(PyNGINXError):
    """Client closed the connection before the request was completed."""


class TLSError(PyNGINXError):
    """TLS handshake or certificate error."""


class HTTPError(PyNGINXError):
    """Base exception for HTTP protocol errors that map to an HTTP status response."""

    status_code: int = 500
    default_message: str = "Internal Server Error"

    def __init__(self, message: str | None = None, status_code: int | None = None) -> None:
        if status_code is not None:
            self.status_code = status_code
        if message is not None:
            self.message = message
        else:
            self.message = self.default_message
        super().__init__(self.message)


class BadRequestError(HTTPError):
    """400 Bad Request: Malformed syntax, invalid headers, missing Host, etc."""

    status_code = 400
    default_message = "Bad Request"


class RequestTimeoutError(HTTPError):
    """408 Request Timeout: Incomplete request before timeout expired."""

    status_code = 408
    default_message = "Request Timeout"


class PayloadTooLargeError(HTTPError):
    """413 Content Too Large: Header or body exceeds configured limits."""

    status_code = 413
    default_message = "Content Too Large"


class UriTooLongError(HTTPError):
    """414 URI Too Long: Request target exceeds configured limits."""

    status_code = 414
    default_message = "URI Too Long"


class NotImplementedHTTPError(HTTPError):
    """501 Not Implemented: Unsupported feature (e.g. Transfer-Encoding in Phase 1)."""

    status_code = 501
    default_message = "Not Implemented"


class HTTPVersionNotSupportedError(HTTPError):
    """505 HTTP Version Not Supported: Requested HTTP version is unsupported."""

    status_code = 505
    default_message = "HTTP Version Not Supported"
