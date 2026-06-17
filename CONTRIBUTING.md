# Contributing to RAYS-CORE

Thanks for contributing. This guide keeps changes reviewable, safe, and reproducible.

## Development Setup

1. Fork and clone.
2. Create a virtual environment.
3. Install editable package.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
python -m pytest tests/ -q
```

Opening a PR runs **GitHub Actions**:

- **Python CLI:** `.github/workflows/ci.yml` — Ubuntu, macOS, Windows (pytest, wheel build).
- **RAYS Studio (when `Electron_app/` changes):** `.github/workflows/studio-ci.yml` — Linux smoke on PR; full matrix on merge to `main`.

See [Versioning and releases](#versioning-and-releases) for Studio release tags (`studio-v*`).

## Branching and PRs

- Use small focused branches.
- Keep PR scope single-purpose when possible.
- Include clear before/after behavior and validation steps.

Suggested branch names:

- `feat/<short-topic>`
- `fix/<short-topic>`
- `docs/<short-topic>`

## Code Quality Expectations

- Prefer minimal, targeted changes.
- Keep provider behavior explicit and testable.
- Avoid introducing hardcoded credentials, tokens, or secrets.
- Preserve cross-platform compatibility (macOS/Linux/Windows).

## Security and Secrets

- Never commit API keys.
- Use environment variables only.
- If a key is exposed accidentally, rotate it immediately.

## Documentation Requirements

For feature changes, update relevant docs:

- `README.md` for user-visible behavior
- `COMMANDS.md` for CLI/slash command changes
- `config.yaml` comments and defaults when config behavior changes

## Testing Checklist (minimum)

Before opening PR:

- Run `python -m pytest tests/ -q` (smoke imports, bytecode compile, config locator).
- Run local install in editable mode (`pip install -e ".[dev]"`).
- Optionally start `rays` and verify startup flow interactively.
- Validate at least one provider path (Ollama or Gemini).
- Verify `/chat`, `/mode`, and one edit pipeline prompt.

## Commit Message Style

Use [Conventional Commits](https://www.conventionalcommits.org/) so maintainers can reason about releases:

| Prefix | Meaning | Studio bump (when labeled `release/studio`) |
|--------|---------|---------------------------------------------|
| `feat:` | New feature | **minor** (1.0.0 → 1.1.0) |
| `fix:` | Bug fix | **patch** (1.0.0 → 1.0.1) |
| `feat!:` or footer `BREAKING CHANGE:` | Breaking change | **major** (1.0.0 → 2.0.0) |
| `docs:`, `chore:`, `refactor:` | No user-facing change | **patch** (or no Studio release) |

Examples:

- `feat: add OpenAI chat/embedding support in AIClient`
- `fix: handle missing provider keys with clear fallback`
- `docs: expand README with pipeline and install guidance`

## Versioning and releases

This repo ships **two products** with **separate version lines**:

| Product | Version file | Tag format | Published to |
|---------|--------------|------------|--------------|
| **RAYS-CORE CLI** (Python) | `pyproject.toml` | `v1.6.0` | [PyPI](https://pypi.org/project/rays-core/) |
| **RAYS Studio** (Electron GUI) | `Electron_app/RAYS-Studio/desktop/package.json` | `studio-v1.0.0` | GitHub Releases (`.dmg`, `.exe`, `.AppImage`, `.deb`) |

### CLI (PyPI)

1. Maintainer bumps `version` in `pyproject.toml` / `setup.py`.
2. Tag `vX.Y.Z` and push.
3. Publish to PyPI (manual or existing release workflow).

### RAYS Studio (desktop installers)

**CI (every PR / merge)** — workflow `.github/workflows/studio-ci.yml`:

- **Pull requests:** Linux build smoke test (validates Electron + PyInstaller).
- **Push to `main`:** Builds macOS, Ubuntu, Windows, and Arch (container), uploads artifacts (not public releases).

**Publishing a Studio release (maintainers):**

1. Merge approved PR(s) to `main`.
2. **Optional auto-bump:** Add label `release/studio` to the merged PR → bot opens a PR bumping `desktop/package.json` → maintainer merges it.
3. **Or bump manually:** Edit `Electron_app/RAYS-Studio/desktop/package.json` `version` field.
4. Create and push a tag (this triggers the release workflow):

   ```bash
   git pull origin main
   git tag studio-v1.0.1
   git push origin studio-v1.0.1
   ```

5. Workflow `.github/workflows/studio-release.yml` builds all platforms and creates a **GitHub Release** with:

   - macOS: `.dmg`
   - Windows: `.exe` (NSIS installer)
   - Ubuntu/Debian: `.AppImage` and `.deb`
   - Arch: `.AppImage` (built in `archlinux` container)

**Manual release (without a local tag):** GitHub → **Actions** → **RAYS Studio Release** → **Run workflow** → enter tag `studio-v1.0.1`.

### GitHub Actions setup (one-time, repo admin)

1. Commit the workflow files under `.github/workflows/`.
2. **Settings → Actions → General → Workflow permissions** → enable **Read and write permissions**.
3. Ensure Actions are enabled for the repository.

## Good First Contributions

- Improve prompt templates and fallback behavior.
- Add provider-specific troubleshooting docs.
- Strengthen error messages and diagnostics.
- Add tests around task analysis and pipeline routing.

