# Changelog

All notable changes to RAYS-CORE will be documented in this file.

## [1.5.2] - 2026-04-25

### Changed
- Confirmed all public repository links point to `https://github.com/markknoffler/RAYS-CORE-CLI`.
- Updated package version to `1.5.2` in `pyproject.toml` and `setup.py`.
- Fixed README clone flow to `cd RAYS-CORE-CLI`.

## [1.0.0] - 2026-04-24

### Added
- Standalone `RAYS-CORE` repository structure.
- Professional OSS documentation (`README`, `CONTRIBUTING`, `SECURITY`).
- Modern Python packaging via `pyproject.toml`.
- Strict `.gitignore` for runtime state, secrets, and build artifacts.

### Changed
- Project metadata aligned for public release and PyPI publishing.
- Documentation expanded for providers, environment setup, modes, prompts, and pipeline.

### Removed
- Local runtime artifacts (`.rays`, `__pycache__`, compiled binaries).
- `trial_codebases` from publish-ready tree.
- Unused Node metadata files.

