# PyInstaller spec: standalone RAYS backend for the desktop app (no separate pip install).
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

spec_dir = Path(SPECPATH).resolve()
desktop_dir = spec_dir.parent
studio_root = desktop_dir.parent
monorepo_root = studio_root.parent.parent
bridge_entry = studio_root / "bridge" / "src" / "rays_bridge" / "ws_bridge.py"
config_yaml = monorepo_root / "src" / "rays_core" / "config.yaml"

pathex = [
    str(monorepo_root / "src"),
    str(studio_root / "bridge" / "src"),
]

datas = [(str(config_yaml), "rays_core")]
binaries = []
hiddenimports = [
    "rays_core",
    "rays_core.rays_main",
    "rays_core.rays_ui",
    "rays_core.config_locator",
    "rays_core.ai_client",
    "rays_core.agent_orchestrator",
    "rays_core.skills_orchestrator",
    "rays_core.mcp_manager",
    "rays_core.mcp_orchestrator",
    "rays_core.mcp_health",
    "rays_core.tool_registry",
    "rays_core.execution_context",
    "rays_core.chroma_client",
    "rays_core.workspace_paths",
    "rays_bridge",
    "websockets",
    "websockets.asyncio",
    "websockets.asyncio.server",
]

for package in ("rays_core", "chromadb", "onnxruntime", "tokenizers", "rich", "yaml", "msgpack", "mcp"):
    try:
        collected = collect_all(package)
        datas += collected[0]
        binaries += collected[1]
        hiddenimports += collected[2]
    except Exception:
        pass

a = Analysis(
    [str(bridge_entry)],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="rays-gui-bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
