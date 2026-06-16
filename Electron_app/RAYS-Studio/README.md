# RAYS Studio (desktop GUI)

All-in-one desktop app: **React UI + Electron shell + Python bridge + RAYS Core**.

| Folder | Purpose |
|--------|---------|
| `ui/` | React / Vite interface |
| `desktop/` | Electron app + `.dmg` build |
| `bridge/` | Python WebSocket bridge (`rays_bridge`) |

Python engine (`rays_core`) is taken from the **monorepo root** (`../../src/rays_core`) when bundling — no duplicate copy in this folder.

## Install from DMG (end users)

1. Download `RAYS Studio-*.dmg` from GitHub Releases (not from git).
2. Drag **RAYS Studio** to Applications and launch.

You still need **Ollama** (local) or **API keys** (cloud) inside the app.

## Build DMG from source

From repository root:

```bash
cd Electron_app/RAYS-Studio
chmod +x build-dmg.sh desktop/scripts/bundle-backend.sh
./build-dmg.sh
```

DMG appears under `desktop/release/`.

## Dev mode (browser)

```bash
# from repo root
pip install -e ".[studio,dev]"
cd Electron_app/RAYS-Studio/ui && npm install && npm run dev
```

## Dev mode (Electron)

```bash
cd Electron_app/RAYS-Studio/ui && npm run dev
# other terminal:
cd Electron_app/RAYS-Studio/desktop && npm install && npm run dev
```

## Fresh install

Each DMG build stamps a unique install epoch. Reinstalling clears saved name, chats, sessions, and workspace list until you use the app again.
