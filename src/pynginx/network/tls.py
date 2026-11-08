"""TLS context configuration and validation for PyNGINX."""

import ssl
from pathlib import Path

from pynginx.errors import TLSError


def create_server_ssl_context(
    cert_path: str | Path,
    key_path: str | Path,
    minimum_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2,
) -> ssl.SSLContext:
    """Creates and configures an SSLContext for HTTPS server termination.
    
    Args:
        cert_path: Path to the PEM-encoded TLS certificate file.
        key_path: Path to the PEM-encoded private key file.
        minimum_version: Minimum allowed TLS protocol version (defaults to TLS 1.2).
        
    Returns:
        Configured ssl.SSLContext ready for asyncio.start_server.
        
    Raises:
        TLSError: If certificates or keys are missing or invalid.
    """
    cert = Path(cert_path).resolve()
    key = Path(key_path).resolve()

    if not cert.is_file():
        raise TLSError(f"TLS certificate file not found: {cert}")

    if not key.is_file():
        raise TLSError(f"TLS private key file not found: {key}")

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = minimum_version
        context.options |= ssl.OP_CIPHER_SERVER_PREFERENCE

        context.load_cert_chain(certfile=str(cert), keyfile=str(key))
        return context
    except ssl.SSLError as exc:
        raise TLSError(f"Failed to load TLS credentials: {exc}") from exc
    except Exception as exc:
        raise TLSError(f"Unexpected TLS configuration error: {exc}") from exc
