"""Authenticated Streamable HTTP entry point for managed MCP hosting."""

import asyncio
import hmac
import logging
import os
from contextlib import asynccontextmanager

from mcp.server import streamable_http
from mcp.server.lowlevel import NotificationOptions
from mcp.server.models import InitializationOptions
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
import uvicorn

import analytics_mcp.coordinator as coordinator


AUTH_TOKEN_ENV = "MCP_AUTH_TOKEN"


def _is_authorized(request: Request) -> bool:
    """Require a Bearer token before forwarding traffic to MCP."""
    expected = os.environ.get(AUTH_TOKEN_ENV)
    provided = request.headers.get("authorization", "")
    return bool(expected) and hmac.compare_digest(provided, f"Bearer {expected}")


async def healthcheck(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": coordinator.app.name})


def create_app() -> Starlette:
    transport = streamable_http.StreamableHTTPServerTransport(
        mcp_session_id=None,
        is_json_response_enabled=False,
    )

    class AuthenticatedMCP:
        async def __call__(self, scope, receive, send) -> None:
            request = Request(scope, receive)
            if not _is_authorized(request):
                await JSONResponse(
                    {"error": "Unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return
            await transport.handle_request(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app: Starlette):
        async with transport.connect() as (read_stream, write_stream):
            task = asyncio.create_task(
                coordinator.app.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name=coordinator.app.name,
                        server_version="1.0.0",
                        capabilities=coordinator.app.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={},
                        ),
                    ),
                )
            )
            try:
                yield
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    return Starlette(
        routes=[
            Route("/health", healthcheck),
            Mount("/mcp", app=AuthenticatedMCP()),
        ],
        lifespan=lifespan,
    )


def run_server() -> None:
    if not os.environ.get(AUTH_TOKEN_ENV):
        raise RuntimeError(f"{AUTH_TOKEN_ENV} must be set")
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    run_server()
