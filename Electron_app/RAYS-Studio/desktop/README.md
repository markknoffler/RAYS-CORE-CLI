# RAYS Studio (Electron)

Desktop shell for the RAYS Studio UI. The UI lives in `rays-code-studio/`; this app loads it and spawns the Python `rays-gui-bridge` against the **canonical** `packages/rays-core-cli` runtime.

## Prerequisites

```bash
# From repo root — install CLI + bridge into your Python env (once)
pip install -e ../..
# from repo root (RAYS-CORE-CLI directory)
```

## Development

Terminal 1 — Vite dev server (session APIs in dev still use Vite middleware unless you point the UI at Electron APIs):

```bash
cd rays-studio/studio && npm run dev
```

Terminal 2 — Electron:

```bash
cd apps/desktop && npm install && npm run dev
```

## Production build

```bash
cd apps/desktop
npm run dist
```

Installers are written to `apps/desktop/release/`.

**Note:** End users need `rays-core` and `rays-gui-bridge` available to Python (bundled installer wiring is a follow-up). `pipx install rays-core` alone does **not** install the desktop app.
