#!/usr/bin/env python3
"""Register OpenWebUI with the remote cluster gateway; save private metadata."""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / '.env'
KEY = 'TOOLHIVE_OAUTH_CLIENT_INFO'


def main() -> None:
    existing = ENV.read_text()
    code = """
import asyncio
from types import SimpleNamespace
from open_webui.utils.oauth import get_oauth_client_info_with_dynamic_client_registration, encrypt_data
async def main():
    info = await get_oauth_client_info_with_dynamic_client_registration(
        SimpleNamespace(base_url="http://127.0.0.1:3000/"),
        "mcp:cluster-tools", "https://cms-compops-mcp-testbed.cern.ch/mcp")
    print("CMSAI_CLIENT_INFO=" + encrypt_data(info.model_dump(mode="json")))
asyncio.run(main())
"""
    result = subprocess.run(
        ['docker', 'compose', 'exec', '-T', 'open-webui', 'python', '-c', code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        diagnostics = ROOT / '.artifacts'
        diagnostics.mkdir(mode=0o700, exist_ok=True)
        fd, path = tempfile.mkstemp(prefix='toolhive-registration-', suffix='.log', dir=diagnostics)
        with os.fdopen(fd, 'w') as log:
            log.write(result.stdout + '\n' + result.stderr)
        raise SystemExit(f'Registration failed. Private diagnostics: {path}; check for credentials before sharing.')
    matches = [
        line.removeprefix('CMSAI_CLIENT_INFO=')
        for line in result.stdout.splitlines()
        if line.startswith('CMSAI_CLIENT_INFO=')
    ]
    if len(matches) != 1 or not matches[0]:
        raise SystemExit('Registration did not return exactly one encrypted client definition.')
    lines = [line for line in existing.splitlines() if not line.startswith(KEY + '=')]
    ENV.write_text('\n'.join(lines) + '\n' + KEY + '=' + matches[0] + '\n')
    os.chmod(ENV, 0o600)
    print('OpenWebUI gateway client registered; encrypted metadata saved in private .env.')
    print('Recreate OpenWebUI with all three Compose files; authorize Cluster Tools (ToolHive) in the chat menu.')


if __name__ == '__main__':
    main()
