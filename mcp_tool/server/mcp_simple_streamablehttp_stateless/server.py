import sys
sys.path.append(r"/usr/local/webapps/mcp/vannaai/src")

import contextlib
import logging
from collections.abc import AsyncIterator

import anyio
import click
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send
from tools import DBTool

logger = logging.getLogger(__name__)


@click.command()
@click.option("--port", default=3001, help="Port to listen on for HTTP")
@click.option(
    "--log-level",
    default="INFO",
    help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "--json-response",
    is_flag=True,
    default=False,
    help="Enable JSON responses instead of SSE streams",
)
def main(
    port: int,
    log_level: str,
    json_response: bool,
) -> int:
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = Server("mcp-streamable-http-stateless-demo")

    @app.call_tool()
    async def call_tool(
        name: str, arguments: dict
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        if name == "add":
            return [
                types.TextContent(
                    type="text",
                    text=str(arguments["a"] + arguments["b"])
                )
            ]
        elif name == "multiply":
            return [
                types.TextContent(
                    type="text",
                    text=str(arguments["a"] * arguments["b"])
                )
            ]
        elif name == "sqltool":
            dbtool = DBTool(arguments)
            return [
                types.TextContent(
                    type="text",
                    text=str(dbtool.execute_query(arguments["query"]))
                )
            ]

        else:
            raise ValueError(f"Tool {name} not found")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="add",
                description="Adds two numbers",
                inputSchema={
                    "type": "object",
                    "required": ["a", "b"],
                    "properties": {
                        "a": {
                            "type": "number",
                            "description": "First number to add",
                        },
                        "b": {
                            "type": "number",
                            "description": "Second number to add",
                        },
                    },
                },
            ),
            types.Tool(
                name="multiply",
                description="Multiplies two numbers",
                inputSchema={
                    "type": "object",
                    "required": ["a", "b"],
                    "properties": {
                        "a": {
                            "type": "number",
                            "description": "First number to multiply",
                        },
                        "b": {
                            "type": "number",
                            "description": "Second number to multiply",
                        },
                    },
                },
            ),
            types.Tool(
                name="sqltool",
                description="research in database by text2sql",
                inputSchema={
                    "type": "object",
                    "required": ["api_url", "api_key","model","host","port","dbname","user","password","dialect",'collection_name'],
                    "properties": {
                        "api_url": {
                            "type": "string",
                            "description": "LLM url",
                        },
                        "api_key": {
                            "type": "string",
                            "description": "LLM key",
                        },
                        "model": {
                            "type": "string",
                            "description": "LLM name",
                        },
                        "host": {
                            "type": "string",
                            "description": "database url",
                        },
                        "port": {
                            "type": "string",
                            "description": "database port",
                        },
                        "dbname": {
                            "type": "string",
                            "description": "database name",
                        },
                        "user": {
                            "type": "string",
                            "description": "database user",
                        },
                        "password": {
                            "type": "string",
                            "description": "LLM key",
                        },
                        "query": {
                            "type": "string",
                            "description": "question from user",
                        },
                        "dialect": {
                            "type": "string",
                            "description": "type of database,such as MySQL or PostgreSQL",
                        },
                        "dsn": {
                            "type": "string",
                            "description": "Only for oracle",
                        },
                        "return_data": {
                            "type": "string",
                            "description": "sql、data、fig、all",
                        },
                        "collection_name": {
                            "type": "string",
                            "description": "sql、data、fig、all",
                        },
                        "is_train": {
                            "type": "string",
                            "description": "sql、data、fig、all",
                        }
                    },
                },
            )
        ]

    # Create the session manager with true stateless mode
    session_manager = StreamableHTTPSessionManager(
        app=app,
        event_store=None,
        json_response=json_response,
        stateless=True,
    )

    async def handle_streamable_http(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Context manager for session manager."""
        async with session_manager.run():
            logger.info("Application started with StreamableHTTP session manager!")
            try:
                yield
            finally:
                logger.info("Application shutting down...")

    # Create an ASGI application using the transport
    starlette_app = Starlette(
        debug=True,
        routes=[
            Mount("/mcp", app=handle_streamable_http),
        ],
        lifespan=lifespan,
    )

    import uvicorn

    uvicorn.run(starlette_app, host="0.0.0.0", port=port)

    return 0

if __name__ == "__main__":
    sys.exit(main())