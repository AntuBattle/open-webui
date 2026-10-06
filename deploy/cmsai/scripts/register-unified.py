#!/usr/bin/env python3
"""Register this Open WebUI deployment with Unified; keep credentials out of Git."""

import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / '.env'
KEY = 'UNIFIED_OAUTH_CLIENT_INFO'


def main():
    existing = ENV.read_text()
    if any(line.startswith(KEY + '=') for line in existing.splitlines()):
        raise SystemExit('Unified is already registered in .env; no registration performed.')
    code = """
import asyncio
from types import SimpleNamespace
from open_webui.utils.oauth import get_oauth_client_info_with_dynamic_client_registration, encrypt_data
async def main():
    info = await get_oauth_client_info_with_dynamic_client_registration(
        SimpleNamespace(base_url='http://127.0.0.1:3000/'),
        'mcp:unified', 'https://cmspnr-api.cern.ch/mcp/sse')
    print('CMSAI_CLIENT_INFO=' + encrypt_data(info.model_dump(mode='json')))
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
        fd, log_path = tempfile.mkstemp(prefix='unified-registration-', suffix='.log', dir=diagnostics)
        with os.fdopen(fd, 'w') as log:
            log.write(result.stdout + '\n' + result.stderr)
        raise SystemExit(
            f'Registration failed. No configuration saved. Private diagnostics: {log_path}. '
            'Do not share this file without checking it for credentials.'
        )
    matches = [
        line.removeprefix('CMSAI_CLIENT_INFO=')
        for line in result.stdout.splitlines()
        if line.startswith('CMSAI_CLIENT_INFO=')
    ]
    if len(matches) != 1 or not matches[0]:
        raise SystemExit('Registration did not return exactly one encrypted client definition.')
    # Environment is an existing private local file, not a tracked configuration file.
    with ENV.open('a') as file:
        file.write('\n' + KEY + '=' + matches[0] + '\n')
    os.chmod(ENV, 0o600)
    print('Unified OAuth client registered and encrypted metadata saved in .env.')
    print('Run docker compose -f compose.yaml -f compose.unified.yaml up -d to enable the configured connection.')


if __name__ == '__main__':
    main()
