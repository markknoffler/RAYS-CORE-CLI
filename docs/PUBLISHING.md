# Publishing RAYS-CORE to PyPI

Maintainer checklist for a **CLI / terminal** release. **Do not publish until tests pass on all CI platforms** (Linux, macOS, Windows).

> **RAYS Studio (GUI)** uses a separate tag and GitHub Releases — see [`STUDIO_RELEASES.md`](./STUDIO_RELEASES.md). CLI tags look like `v1.6.0`; Studio tags look like `studio-v1.0.0`.

## Pre-release

1. **Version** — bump `version` in both `pyproject.toml` and `setup.py` (keep them in sync).
2. **Changelog** — move `[Unreleased]` entries under a dated `[x.y.z]` section in `CHANGELOG.md`.
3. **Tests locally:**

   ```bash
   python -m pip install -e ".[dev]"
   python -m pytest tests/ -q
   python -m build
   twine check dist/*
   ```

4. **Smoke install** (optional but recommended):

   ```bash
   pipx install --force dist/rays_core-*.whl   # or pip install dist/*.whl in a venv
   rays --help
   ```

5. **Git** — commit release prep, tag, push (you do this; the agent does not push unless asked):

   ```bash
   git add pyproject.toml setup.py CHANGELOG.md
   git commit -m "Release v1.6.0"
   git tag v1.6.0
   git push origin v1.6.0
   ```

   Wait for the **PyPI Release** workflow (`.github/workflows/pypi-release.yml`) to verify tests on all three OSes and upload to PyPI.

   Repository secret required: `PYPI_API_TOKEN` (PyPI API token with upload scope).

## Publish to PyPI (manual fallback)

If you prefer a manual upload instead of the GitHub Action:

PyPI credentials: API token via `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<pypi-token>`, or `~/.pypirc`.

```bash
python -m pip install --upgrade build twine
rm -rf dist/ build/ *.egg-info
python -m build
twine check dist/*
twine upload dist/*
```

TestPyPI (optional dry run):

```bash
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ rays-core==1.6.0
```

## Post-release

1. Confirm [pypi.org/project/rays-core](https://pypi.org/project/rays-core/) shows the new version.
2. Users install with: `pipx install rays-core` or `pip install -U rays-core`.
3. Open a new `[Unreleased]` section in `CHANGELOG.md` for the next cycle.

## What ships in the wheel

- Python package under `src/rays_core/` including bundled `config.yaml`
- CLI entrypoint: `rays` → `rays_core.rays_main:main`
- **Not** included: `examples/`, `skills/docx/node_modules`, local `.rays` state, or user `~/.rays/` config

## Windows notes (agent orchestrator path)

The `/code` pipeline has its own path handling. The **default agent orchestrator** (skills + MCP) uses `workspace_paths.resolve_workspace_path()` so model-supplied paths with `/` or `\` resolve correctly on Windows. CI runs on `windows-latest` to catch regressions.
