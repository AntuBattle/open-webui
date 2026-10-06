#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .artifacts
# Match OpenWebUI's .github/workflows/docker.yaml preparation step.
awk '
  /^FROM --platform=\$BUILDPLATFORM node:/ {
    print
    print "ENV NODE_OPTIONS=\"--max-old-space-size=12288\""
    next
  }
  { print }
' ../../Dockerfile > .artifacts/OpenWebUI.Dockerfile
docker compose build "$@"
