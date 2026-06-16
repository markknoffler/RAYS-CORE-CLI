# RAYS Studio (Electron GUI)

Desktop GUI for RAYS-CORE. **Source lives here** so anyone can build from GitHub; installers are published separately as GitHub releases.

| Path | Purpose |
|------|---------|
| [RAYS-Studio/](RAYS-Studio/) | React UI, Electron shell, WebSocket bridge |

## Build installers

| Platform | Command (`cd Electron_app/RAYS-Studio` first) |
|----------|-----------------------------------------------|
| macOS | `chmod +x build-dmg.sh && ./build-dmg.sh` |
| Linux (Ubuntu) | `chmod +x build-linux.sh && ./build-linux.sh` |
| Windows | `powershell -ExecutionPolicy Bypass -File build-windows.ps1` |

PyInstaller backend binaries are **platform-specific** — build on the target OS (or use GitHub Actions workflow `.github/workflows/studio-release.yml`).

## Build from source (macOS DMG)

From the **repository root**:

```bash
cd Electron_app/RAYS-Studio
chmod +x build-dmg.sh desktop/scripts/bundle-backend.sh
./build-dmg.sh
```

Output: `Electron_app/RAYS-Studio/desktop/release/*.dmg`

Requirements: Node 18+, Python 3.10+, Xcode command-line tools (for signing-less local builds).

The build bundles `rays_core` from the monorepo root (`pip install -e ".[studio,dev]"`) and packages the UI + Python bridge with PyInstaller.

## Dev mode (browser)

```bash
pip install -e ".[studio,dev]"
cd Electron_app/RAYS-Studio/ui && npm install && npm run dev
```

Open http://127.0.0.1:8080

## Dev mode (Electron window)

```bash
cd Electron_app/RAYS-Studio/ui && npm run dev
# other terminal:
cd Electron_app/RAYS-Studio/desktop && npm install && npm run dev
```

## What not to commit

- `node_modules/`, `ui/dist/`, `desktop/release/`, `*.dmg`
- `desktop/resources/backend/` (PyInstaller output)
- `RAYS-CORE-GUI/` (local duplicate copy — ignored)

## Fresh install behavior

Each DMG build embeds a unique install epoch. Reinstalling the app clears chats, sessions, saved name, and workspace history so new users start with a blank slate.
