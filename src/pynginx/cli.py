"""Command-line interface for PyNGINX."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from pynginx.network.server import PyNGINXServer
from pynginx.network.tls import create_server_ssl_context


def setup_logging(level: str = "INFO") -> None:
    """Configures structured console logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args(args=None) -> argparse.Namespace:
    """Parses command-line options."""
    parser = argparse.ArgumentParser(
        prog="pynginx",
        description="PyNGINX: Python-only reverse proxy and load balancer",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8443,
        help="Port to listen on (default: 8443)",
    )
    parser.add_argument(
        "--cert",
        default="certs/server.crt",
        help="Path to TLS certificate file (default: certs/server.crt)",
    )
    parser.add_argument(
        "--key",
        default="certs/server.key",
        help="Path to TLS private key file (default: certs/server.key)",
    )
    parser.add_argument(
        "--no-tls",
        action="store_true",
        help="Run without TLS (plaintext HTTP/1.1)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)",
    )
    return parser.parse_args(args)


async def async_main(args: argparse.Namespace) -> None:
    """Main async entry point starting PyNGINX server."""
    setup_logging(args.log_level)
    logger = logging.getLogger("pynginx")

    ssl_ctx = None
    if not args.no_tls:
        cert_path = Path(args.cert)
        key_path = Path(args.key)
        if not cert_path.is_file() or not key_path.is_file():
            logger.error(
                "TLS certificate (%s) or key (%s) not found. "
                "Run scripts/generate_dev_cert.ps1 (or .sh) first, or pass --no-tls.",
                cert_path,
                key_path,
            )
            sys.exit(1)

        ssl_ctx = create_server_ssl_context(cert_path, key_path)

    server = PyNGINXServer(
        host=args.host,
        port=args.port,
        ssl_context=ssl_ctx,
    )

    await server.start()
    scheme = "http" if args.no_tls else "https"
    logger.info("PyNGINX running at %s://%s:%d/ (Press Ctrl+C to stop)", scheme, args.host, server.bound_port)

    stop_event = asyncio.Event()

    try:
        # Keep serving until cancelled
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Stopping PyNGINX server...")
        await server.stop()


def main() -> None:
    """Synchronous entry point."""
    args = parse_args()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
