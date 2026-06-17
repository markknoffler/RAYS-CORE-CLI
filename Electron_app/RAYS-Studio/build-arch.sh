#!/usr/bin/env bash
# Build RAYS Studio on Arch Linux (AppImage). Used in CI via archlinux container.
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
echo "Arch/Linux artifacts under: $ROOT/desktop/release"
ls -la "$ROOT/desktop/release/" || true
