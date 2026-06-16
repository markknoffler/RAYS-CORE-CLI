#!/usr/bin/env bash
# Build RAYS Studio for Linux (AppImage + deb). Run on Ubuntu/Debian (or CI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
EPOCH=$(date +%s)
echo "{\"epoch\":\"$EPOCH\"}" > "$ROOT/desktop/electron/install-epoch.json"
echo "==> Install epoch for this build: $EPOCH"
cd "$ROOT/ui" && npm ci && npm run build
cd "$ROOT/desktop"
npm ci
chmod +x scripts/bundle-backend.sh
npm run dist:linux
echo "Linux artifacts under: $ROOT/desktop/release"
ls -la "$ROOT/desktop/release"/*.{AppImage,deb} 2>/dev/null || ls -la "$ROOT/desktop/release/"
