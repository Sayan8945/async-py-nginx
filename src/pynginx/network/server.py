"""Asynchronous TCP listener and TLS termination server for PyNGINX."""

import asyncio
import logging
import ssl
from collections.abc import Awaitable, Callable

from pynginx.errors import (
    ClientDisconnectedError,
    HTTPError,
)
from pynginx.protocol.http_models import HTTPRequest, HTTPResponse
from pynginx.protocol.http_parser import HTTPParser
from pynginx.protocol.serializer import HTTPResponseSerializer

logger = logging.getLogger("pynginx.server")

HandlerType = Callable[[HTTPRequest], Awaitable[HTTPResponse]]


async def default_request_handler(request: HTTPRequest) -> HTTPResponse:
    """Default handler returning a valid JSON HTTP/1.1 response."""
    payload = {
        "status": "ok",
        "message": "Welcome to PyNGINX",
        "method": request.method,
        "target": request.target,
        "version": request.version,
        "body_length": len(request.body),
    }
    return HTTPResponseSerializer.create_json_response(200, payload)


class PyNGINXServer:
    """Asyncio TCP server supporting TLS termination and HTTP/1.1 request handling."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8443,
        ssl_context: ssl.SSLContext | None = None,
        handler: HandlerType | None = None,
        max_request_line_bytes: int = HTTPParser.DEFAULT_MAX_REQUEST_LINE_BYTES,
        max_header_bytes: int = HTTPParser.DEFAULT_MAX_HEADER_BYTES,
        max_body_bytes: int = HTTPParser.DEFAULT_MAX_BODY_BYTES,
        request_timeout: float = 15.0,
        ssl_handshake_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.handler = handler or default_request_handler
        self.request_timeout = request_timeout
        self.ssl_handshake_timeout = ssl_handshake_timeout

        self.parser = HTTPParser(
            max_request_line_bytes=max_request_line_bytes,
            max_header_bytes=max_header_bytes,
            max_body_bytes=max_body_bytes,
            request_timeout=request_timeout,
        )

        self._server: asyncio.Server | None = None
        self._active_connections: set[asyncio.Task] = set()

    @property
    def bound_port(self) -> int:
        """Returns the actual bound port (useful when port 0 is used for ephemeral binding)."""
        if self._server and self._server.sockets:
            return self._server.sockets[0].getsockname()[1]
        return self.port

    async def start(self) -> None:
        """Starts the TCP server listener."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            ssl=self.ssl_context,
            ssl_handshake_timeout=self.ssl_handshake_timeout if self.ssl_context else None,
        )
        logger.info(
            "PyNGINX server listening on %s:%d (TLS=%s)",
            self.host,
            self.bound_port,
            self.ssl_context is not None,
        )

    async def stop(self) -> None:
        """Gracefully shuts down the server and active connections."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

        # Cancel any active connection handlers
        if self._active_connections:
            for task in list(self._active_connections):
                task.cancel()
            await asyncio.gather(*self._active_connections, return_exceptions=True)
            self._active_connections.clear()

        logger.info("PyNGINX server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Connection handler processing a client connection."""
        task = asyncio.current_task()
        if task:
            self._active_connections.add(task)
            task.add_done_callback(self._active_connections.discard)

        peername = writer.get_extra_info("peername")
        logger.debug("New connection from %s", peername)

        try:
            try:
                request = await self.parser.read_request(reader)
                response = await self.handler(request)
            except ClientDisconnectedError:
                logger.debug("Client %s disconnected cleanly before request completed", peername)
                return
            except HTTPError as http_err:
                logger.warning(
                    "HTTP protocol error from %s: [%d] %s",
                    peername,
                    http_err.status_code,
                    http_err.message,
                )
                response = HTTPResponseSerializer.create_error_response(
                    status_code=http_err.status_code,
                    message=http_err.message,
                )
            except TimeoutError:
                logger.warning("Request read timeout from %s", peername)
                response = HTTPResponseSerializer.create_error_response(
                    status_code=408,
                    message="Request Timeout",
                )
            except ssl.SSLError as ssl_err:
                logger.warning("TLS error from %s: %s", peername, ssl_err)
                return
            except Exception:
                logger.exception("Unexpected server error processing request from %s", peername)
                response = HTTPResponseSerializer.create_error_response(
                    status_code=500,
                    message="Internal Server Error",
                )

            # Send response and close connection cleanly (Phase 1 scope: one request per connection)
            response_bytes = HTTPResponseSerializer.serialize(
                response, default_connection_close=True
            )
            writer.write(response_bytes)
            await writer.drain()

        except (ConnectionResetError, BrokenPipeError):
            logger.debug("Client %s abruptly closed connection during transmission", peername)
        except OSError as exc:
            logger.debug("Error during connection cleanup for %s: %s", peername, exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except OSError as close_err:
                logger.debug("Error while closing connection for %s: %s", peername, close_err)
            logger.debug("Connection closed for %s", peername)
