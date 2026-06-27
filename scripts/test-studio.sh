#!/usr/bin/env bash
# Run RAYS Studio GUI tests (Python bridge + React UI).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Python bridge tests"
python -m pip install -q -e ".[studio,dev]"
python -m pytest tests/test_studio_bridge.py -q

echo "==> React UI tests (vitest)"
cd Electron_app/RAYS-Studio/ui
npm ci --silent
npm test

echo "==> All Studio tests passed"
