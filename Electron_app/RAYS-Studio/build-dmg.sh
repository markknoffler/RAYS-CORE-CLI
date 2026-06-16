#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
EPOCH=$(date +%s)
echo "{\"epoch\":\"$EPOCH\"}" > "$ROOT/desktop/electron/install-epoch.json"
echo "==> Install epoch for this build: $EPOCH"
cd "$ROOT/ui" && npm ci && npm run build
cd "$ROOT/desktop"
npm ci
chmod +x scripts/bundle-backend.sh
npm run dist:mac
echo "DMG output under: $ROOT/desktop/release"
ls -la "$ROOT/desktop/release"/*.dmg 2>/dev/null || true
