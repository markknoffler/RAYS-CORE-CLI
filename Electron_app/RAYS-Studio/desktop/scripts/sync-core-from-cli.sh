#!/usr/bin/env bash
# Clone RAYS-CORE-CLI core into RAYS-Studio/src/rays_core (GUI backend source of truth).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_CORE="$REPO_ROOT/RAYS-CORE-CLI/src/rays_core"
STUDIO_CORE="$REPO_ROOT/src/rays_core"

if [[ ! -d "$CLI_CORE" ]]; then
  echo "ERROR: Missing $CLI_CORE" >&2
  exit 1
fi

rsync -av --delete \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  "$CLI_CORE/" "$STUDIO_CORE/"

echo "Synced $CLI_CORE -> $STUDIO_CORE"
