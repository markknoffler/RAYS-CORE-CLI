#!/usr/bin/env bash
# Bundle rays-core + bridge into a single executable for the desktop app (out-of-box, no pip).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STUDIO_ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
MONOREPO_ROOT="$(cd "$STUDIO_ROOT/../.." && pwd)"
BACKEND_OUT="$DESKTOP_DIR/resources/backend"
WORK_DIR="$DESKTOP_DIR/resources/backend-build"
VENV_DIR="$DESKTOP_DIR/resources/bundle-venv"

echo "==> RAYS Studio: bundling Python backend"
echo "    Studio: $STUDIO_ROOT"
echo "    Monorepo: $MONOREPO_ROOT"

rm -rf "$BACKEND_OUT" "$WORK_DIR"
mkdir -p "$BACKEND_OUT"

cd "$MONOREPO_ROOT"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

pip install -q -U pip wheel
pip install -q -e ".[studio,dev]"
# chromadb's default embedding function requires onnxruntime at import time
pip install -q "onnxruntime>=1.16,<2" "tokenizers>=0.15,<1"

pyinstaller "$DESKTOP_DIR/pyinstaller/rays-bridge.spec" \
  --distpath "$BACKEND_OUT" \
  --workpath "$WORK_DIR" \
  --noconfirm

BACKEND_BIN="rays-gui-bridge"
if [[ -f "$BACKEND_OUT/rays-gui-bridge.exe" ]]; then
  BACKEND_BIN="rays-gui-bridge.exe"
fi

if [[ ! -f "$BACKEND_OUT/$BACKEND_BIN" ]]; then
  echo "ERROR: PyInstaller did not produce $BACKEND_OUT/$BACKEND_BIN" >&2
  exit 1
fi

chmod +x "$BACKEND_OUT/$BACKEND_BIN" 2>/dev/null || true
echo "==> Backend bundle ready: $BACKEND_OUT/$BACKEND_BIN"
ls -lh "$BACKEND_OUT/$BACKEND_BIN"
