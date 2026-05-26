# Troubleshooting

## CLI / startup

### `config.yaml not found`

- Install from PyPI/Git should ship or resolve `config.yaml`. If missing, pass an explicit config:  
  `rays --config /absolute/path/to/config.yaml`
- For development, run from the repository root so the bundled file is discoverable, or clone the repo locally.

### Ollama not reachable / provider warnings

- Default Ollama URL is typically `http://localhost:11434`. Start Ollama and ensure the daemon is listening before selecting the local provider in the launcher.

### Gemini / API keys

- Prefer environment variables (`GEMINI_API_KEY` or `GOOGLE_API_KEY`). Keys are intentionally not persisted in YAML.

### Import or `rays` command not found (pip/pipx)

- **pipx:** `pipx ensurepath`, open a new shell, run `rays`.
- **pip:** ensure your Python Scripts / `bin` directory is on `PATH`.

## CI / contributing

See **CONTRIBUTING.md** — opening a PR runs GitHub Actions (install, pytest, package build sanity) on Ubuntu, macOS, and Windows.

## Still stuck?

Open an issue with logs (no secrets): [Issues](https://github.com/markknoffler/RAYS-CORE-CLI/issues).
