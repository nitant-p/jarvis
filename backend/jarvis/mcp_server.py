"""Private stdio server. Only read and proposal tools; no approval capability."""

import asyncio
import json

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from jarvis.calendar import CalendarService
from jarvis.config import Settings
from jarvis.db import Database
from jarvis.tools import DEFINITIONS, ToolRegistry


async def main():
    settings = Settings()
    db = Database(settings)
    registry = ToolRegistry(CalendarService(db, settings.source_job_id))
    server = Server("jarvis-calendar")

    @server.list_tools()
    async def list_tools():
        return [
            types.Tool(name=name, description=description, inputSchema=schema.model_json_schema())
            for name, (schema, description) in DEFINITIONS.items()
        ]

    @server.call_tool()
    async def call_tool(name, arguments):
        result = registry.call(name, arguments)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result))],
            structuredContent=result,
        )

    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
