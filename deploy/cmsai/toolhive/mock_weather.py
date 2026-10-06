"""Deterministic Geneva weather MCP for the local ToolHive trial."""

from enum import StrEnum

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel


class DataSource(StrEnum):
    MOCK = 'mock'


class Temperature(BaseModel):
    city: str
    temperature_celsius: float
    source: DataSource


mcp = FastMCP(
    'Geneva Weather Mock',
    instructions='Weather results are simulated test data, never live observations.',
    host='127.0.0.1',
    port=18484,
    stateless_http=True,
    json_response=True,
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def get_geneva_temperature() -> Temperature:
    """Return the simulated temperature of Geneva: always 20 degrees Celsius."""
    return Temperature(city='Geneva', temperature_celsius=20.0, source=DataSource.MOCK)


if __name__ == '__main__':
    mcp.run(transport='streamable-http')
