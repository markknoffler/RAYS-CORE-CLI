# RAYS Studio — GitHub Releases

RAYS Studio is the **desktop GUI** for RAYS-CORE. Installers are published on the [GitHub Releases](https://github.com/markknoffler/RAYS-CORE-CLI/releases) page — **not** on PyPI.

The **CLI** (`rays` command) is published separately to [PyPI](https://pypi.org/project/rays-core/). See [`PUBLISHING.md`](./PUBLISHING.md).

## Download (end users)

1. Open [GitHub Releases](https://github.com/markknoffler/RAYS-CORE-CLI/releases).
2. Find the latest **RAYS Studio** release (tag `studio-vX.Y.Z`).
3. Download the installer for your platform:

| Platform | File | Install |
|----------|------|---------|
| macOS | `.dmg` | Open DMG, drag **RAYS Studio** to Applications |
| Windows | `.exe` (NSIS) | Run the installer |
| Ubuntu / Debian | `.deb` | `sudo dpkg -i RAYS-Studio_*.deb` (install deps if needed) |
| Any Linux | `.AppImage` | `chmod +x` then run |
| Arch Linux | `.pkg.tar.zst` | `sudo pacman -U RAYS-Studio-*.pkg.tar.zst` |

4. Launch the app and configure **Ollama** (local) or an **API key** (cloud) in Settings.

Portable `.zip` builds may also be attached for macOS and Windows.

## Release tags (maintainers)

Two independent release channels:

| Product | Tag format | Workflow | Destination |
|---------|------------|----------|-------------|
| **CLI** (`rays-core`) | `v1.6.0` | `.github/workflows/pypi-release.yml` | [PyPI](https://pypi.org/project/rays-core/) |
| **RAYS Studio GUI** | `studio-v1.0.0` | `.github/workflows/studio-release.yml` | GitHub Releases |

Tags are **not interchangeable**. Pushing `v1.6.0` does not build the GUI; pushing `studio-v1.0.0` does not publish to PyPI.

### Publish a new RAYS Studio version

1. Bump `version` in `Electron_app/RAYS-Studio/desktop/package.json` (or merge an automated bump PR from the `release/studio` label workflow).
2. Commit and push to `main`.
3. Tag and push:

   ```bash
   git tag studio-v1.0.1
   git push origin studio-v1.0.1
   ```

4. Wait for the **RAYS Studio Release** workflow. It builds macOS, Windows, Ubuntu, and Arch artifacts and creates/updates the GitHub Release.

Manual trigger: **Actions → RAYS Studio Release → Run workflow** (enter `studio-vX.Y.Z`).

### Publish a new CLI version (PyPI)

See [`PUBLISHING.md`](./PUBLISHING.md). Summary:

```bash
# After bumping pyproject.toml + setup.py and merging to main:
git tag v1.6.1
git push origin v1.6.1
```

Requires repository secret `PYPI_API_TOKEN` and a GitHub **pypi** environment (for trusted publishing, optional).

## CI (no release)

- **RAYS Studio CI** (`.github/workflows/studio-ci.yml`) — GUI tests + build smoke on PRs; full matrix on `main`.
- **CI** (`.github/workflows/ci.yml`) — CLI pytest on all OSes; does not publish.

## Local build from source

```bash
cd Electron_app/RAYS-Studio
chmod +x build-dmg.sh build-linux.sh build-arch.sh desktop/scripts/bundle-backend.sh
./build-dmg.sh      # macOS
./build-linux.sh    # Ubuntu/Debian
./build-arch.sh     # Arch (pacman + AppImage)
# Windows: powershell -ExecutionPolicy Bypass -File build-windows.ps1
```

## Local GUI tests

```bash
# Python bridge
python -m pip install -e ".[studio,dev]"
python -m pytest tests/test_studio_bridge.py -q

# React UI (Vitest)
cd Electron_app/RAYS-Studio/ui && npm ci && npm test
```
