"""Exercise the real mock and gateway MCP endpoints; fail on contract changes."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthMetadata, ProtectedResourceMetadata
from mcp.shared.exceptions import McpError
from mcp.types import TextContent


async def verify(url: str, tool_name: str, token: str | None = None) -> None:
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    async with (
        httpx.AsyncClient(headers=headers, timeout=60) as client,
        streamable_http_client(url, http_client=client) as (read, write, _),
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            if token:
                while tools.nextCursor:
                    tools = await session.list_tools(cursor=tools.nextCursor)
                    names.extend(tool.name for tool in tools.tools)
                assert tool_name in names, names
                assert any(name.startswith('unified_') for name in names), names
                assert all(name == tool_name or name.startswith('unified_') for name in names), names
                print(f'PASS authenticated gateway discovery: weather + {len(names) - 1} Unified tools')
                ping = await session.call_tool('unified_health_check_ping', {})
                assert not ping.isError, ping
                assert len(ping.content) == 1 and isinstance(ping.content[0], TextContent), ping
                assert json.loads(ping.content[0].text) == {'message': 'pong', 'status': 'ok'}, ping
                print('PASS authenticated Unified MCP ping through the gateway: pong/ok')
            else:
                assert names == [tool_name], tools
            for _ in range(2):
                result = await session.call_tool(tool_name, {})
                assert not result.isError, result
                assert result.structuredContent == {
                    'city': 'Geneva',
                    'temperature_celsius': 20.0,
                    'source': 'mock',
                }, result
                assert len(result.content) == 1, result
                assert isinstance(result.content[0], TextContent), result
            if tool_name == 'get_geneva_temperature':
                invalid = await session.call_tool('unknown_weather_tool', {})
                assert invalid.isError, invalid
            else:
                try:
                    await session.call_tool('unknown_weather_tool', {})
                except McpError as error:
                    assert error.error.message == 'tool "unknown_weather_tool" not found', error
                else:
                    raise AssertionError('Gateway accepted an unknown tool')
    print(f'PASS {url}: {tool_name}, fixed mock payload, repeated calls, unknown-tool rejection')


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--gateway-token-file',
        type=Path,
        help='Private file containing a token obtained through the normal gateway OAuth flow',
    )
    args = parser.parse_args()
    await verify('http://127.0.0.1:18484/mcp', 'get_geneva_temperature')
    async with httpx.AsyncClient() as client:
        metadata = OAuthMetadata.model_validate(
            (await client.get('http://127.0.0.1:4483/.well-known/oauth-authorization-server')).raise_for_status().json()
        )
        assert str(metadata.issuer) == 'http://127.0.0.1:4483/', metadata
        assert str(metadata.authorization_endpoint) == 'http://127.0.0.1:4483/oauth/authorize', metadata
        resource = ProtectedResourceMetadata.model_validate(
            (await client.get('http://127.0.0.1:4483/.well-known/oauth-protected-resource/mcp'))
            .raise_for_status()
            .json()
        )
        assert str(resource.resource) == 'http://127.0.0.1:4483/mcp', resource
        for headers in ({}, {'Authorization': 'Bearer invalid-token'}):
            response = await client.post(
                'http://127.0.0.1:4483/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list'}
            )
            assert response.status_code == 401, response.status_code
            assert (
                'resource_metadata="http://127.0.0.1:4483/.well-known/oauth-protected-resource/mcp"'
                in response.headers['www-authenticate']
            )
    print('PASS gateway OAuth discovery, missing-token rejection and invalid-token rejection')
    if args.gateway_token_file:
        token = args.gateway_token_file.read_text().strip()
        assert token, 'Gateway token file is empty'
        await verify('http://127.0.0.1:4483/mcp', 'weather_get_geneva_temperature', token)
    else:
        print('Authenticated gateway tool discovery/calls require --gateway-token-file; not checked by this run')


if __name__ == '__main__':
    asyncio.run(main())
