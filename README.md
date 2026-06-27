<p align="center">
  <strong><img width="305" height="101" alt="Screenshot 2026-04-25 at 4 22 11 PM" src="https://github.com/user-attachments/assets/47a81199-ad05-49fc-8df0-2918508dac34" />
</strong><br/>
  <strong>Open-source AI coding assistant for real repositories.</strong><br/>
  Index. Analyze. Plan. Edit. Ship.
</p>

<p align="center">
  <a href="https://github.com/markknoffler/RAYS-CORE-CLI/actions"><img alt="build" src="https://img.shields.io/github/actions/workflow/status/markknoffler/RAYS-CORE-CLI/ci.yml?branch=main&label=build"></a>
  <a href="https://pypi.org/project/rays-core/"><img alt="pypi" src="https://img.shields.io/pypi/v/rays-core"></a>
  <a href="https://pypi.org/project/rays-core/"><img alt="python" src="https://img.shields.io/pypi/pyversions/rays-core"></a>
  <a href="https://pypi.org/project/rays-core/"><img alt="downloads" src="https://img.shields.io/pypi/dm/rays-core"></a>
  <a href="./LICENSE"><img alt="license" src="https://img.shields.io/badge/license-MIT-green"></a>
</p>

---

## Preview

<img width="1469" height="872" alt="Screenshot 2026-04-25 at 4 17 25 PM" src="https://github.com/user-attachments/assets/481788ed-20d8-45ba-bce6-459ade35b960" />



<img width="1469" height="872" alt="Screenshot 2026-04-25 at 4 18 46 PM" src="https://github.com/user-attachments/assets/869fda6c-5a07-4d8b-ab16-d44b1b0b0400" />


RAYS-CORE is an AI coding assistant for local repositories. It indexes your codebase, retrieves relevant symbols and files, plans changes, applies edits with permission controls, and maintains persistent project memory.

## Why RAYS-CORE

- Works on real codebases with structural indexing and symbol-level retrieval.
- Supports read-only chat, targeted editing, and new-project generation in one CLI.
- Provider-flexible: local-first with Ollama, plus Gemini API support.
- Tracks context over time through `.rays` memory and summaries.

## Features

- **Default agent orchestrator**: skills + MCP servers with dynamic sub-agents, live HUD, and session summary (`/mcp` for server status).
- Codebase indexing (`files`, `symbols`, `relationships`, `boundaries`) via msgpack registries.
- ChromaDB-backed vector retrieval for relevant chunks.
- Multi-stage **`/code`** edit pipeline: task analysis -> selection -> planning -> permissions -> apply.
- Interactive slash commands (`/chat`, `/code`, `/model`, `/mode`, `/git`, `/mcp`, `/help`).
- Session-aware API key handling (reads env vars first; never persists keys in `config.yaml`).

## Supported Providers

- **Ollama (local)**
  - Default local endpoint: `http://localhost:11434`
  - By default, RAYS expects Ollama to be running on port `11434` unless you configure a different endpoint.
- **Gemini API**
  - Uses `GEMINI_API_KEY` (or fallback `GOOGLE_API_KEY`).

Some builds may still show additional provider options in the selector, but this repository release is documented and supported around Ollama and Gemini.

## Environment Variables

RAYS checks environment variables before prompting for API keys.

- `GEMINI_API_KEY`: Gemini API key (preferred for Gemini)
- `GOOGLE_API_KEY`: Gemini fallback key if `GEMINI_API_KEY` is not set

### macOS/Linux (zsh/bash)

```bash
export GEMINI_API_KEY="your_gemini_key"
```

To make permanent in zsh:

```bash
echo 'export GEMINI_API_KEY="your_gemini_key"' >> ~/.zshrc
source ~/.zshrc
```

### Windows (PowerShell)

```powershell
setx GEMINI_API_KEY "your_gemini_key"
```

Open a new terminal after `setx`.

## Installation

### Option A: pipx (recommended for CLI users)

```bash
pipx install rays-core
```

Upgrade later with:

```bash
pipx upgrade rays-core
```

### Option B: pip

```bash
pip install rays-core
```

Upgrade later with:

```bash
pip install --upgrade rays-core
```

### Development install from source

```bash
git clone https://github.com/markknoffler/RAYS-CORE-CLI.git
cd RAYS-CORE-CLI
python -m pip install -e .
```

## Quick Start

```bash
rays /path/to/your/codebase
```

Or inside a repository:

```bash
cd /path/to/your/codebase
rays
```

## Operating modes

RAYS-CORE supports these workflow modes:

1. **Agent orchestrator (default prompt)**
   - Trigger: normal prompt without `/chat` or `/code`.
   - Behavior: discovers **skills** (`skills/`, `~/.rays/skills/`) and **MCP servers** (`config.yaml` → `~/.rays/mcp.json` → `<project>/.rays/mcp.json`), plans spawn steps, runs dynamic sub-agents. Use for Blender, documents, GitHub MCP, and local file/shell tasks.
   - Docs: [`docs/SKILLS.md`](./docs/SKILLS.md) · [`docs/MCP_SERVERS.md`](./docs/MCP_SERVERS.md)

2. **Editing mode (`/code`)**
   - Trigger: `/code` then your prompt (or legacy full coding pipeline where enabled).
   - Behavior: analyzes task, identifies symbols/files, negotiates permissions, plans edits, applies changes.

3. **New codebase generation mode**
   - Trigger: prompts that clearly request creating a new project and low structural dependency on existing code.
   - Behavior: sets up project structure, negotiates creation scope, generates files iteratively.

4. **Chat mode (`/chat`)**
   - Trigger: `/chat <question>`.
   - Behavior: read-only contextual Q&A; no edit pipeline.

## Prompting Guide

### Agent orchestrator prompts (default — no slash command)

- "Add icing and sprinkles to the doughnut in Blender."
- "List this project's top-level files and summarize the README."
- "Create a Word doc from `notes.md` in this folder."

### Editing mode prompts (`/code`)

- "Refactor authentication middleware to support JWT refresh tokens."
- "Fix the bug where user profile update fails on missing avatar."
- "Add caching around `get_project_metrics` and include invalidation."

### New codebase creation prompts

- "Create a new FastAPI project with JWT auth, PostgreSQL, and Alembic migrations."
- "Generate a minimal React + TypeScript dashboard app with routing and auth pages."

### Chat mode prompts

Use:

```text
/chat how does the permission negotiation pipeline work in this repo?
```

## Slash Commands

- `/help` - show commands
- `/chat <question>` - read-only contextual Q&A
- `/model <name>` - switch model
- `/mode auto` - autonomous command execution
- `/mode ask` - ask-permission command execution
- `/git` - summarize current git changes
- `/mcp` - list MCP servers and connection status (agent orchestrator)
- `/clear` - clear screen
- `/exit` - exit RAYS

## Execution Behavior (`/mode`)

- **Ask mode**: requests confirmation for terminal actions.
- **Autonomous mode**: executes without per-command confirmation.

## Pipeline Architecture

1. **Provider + model selection**
2. **Indexing** of files/symbols/relationships/boundaries
3. **Vector DB sync** for semantic retrieval
4. **Task analysis** (intent, scope, terminal needs)
5. **Symbol detection** and candidate retrieval
6. **Planning** and permission negotiation
7. **Anchoring + code generation**
8. **Execution** and post-edit terminal actions
9. **Memory + summary persistence**

Core modules (`src/rays_core/`):

- `rays_main.py` - orchestrator and CLI loop
- `task_analyzer.py` - intent and scope analysis
- `symbol_detection.py` - symbol selection and retrieval
- `planning.py` - implementation planning
- `execution.py` + `code_generator.py` - code application
- `memory.py` - persistent memory and summaries

## Configuration

Primary configuration file: `config.yaml`

Key sections:

- `llm` - provider, model, endpoint, runtime key override
- `embedding` - embedding provider/model/endpoint
- `execution_mode` - default `ask` or `autonomous`

`config.yaml` values are startup defaults. During CLI startup, selected provider/model values are updated and persisted automatically.

RAYS intentionally clears persisted API keys in config and uses runtime/session keys.

## Contributing

Contributions are welcome. Start with [`CONTRIBUTING.md`](./CONTRIBUTING.md) for setup, branch hygiene, and PR expectations.

Pull requests run **automated CI** (install → pytest → package build checks) on **Linux, macOS, and Windows** via GitHub Actions (see [.github/workflows/ci.yml](./.github/workflows/ci.yml)). You only need to push the workflow YAML in this repo — no extra dashboard setup unless Actions are disabled in repository settings.

**More docs:** [`ROADMAP.md`](./ROADMAP.md) · [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/SKILLS.md`](./docs/SKILLS.md) · [`docs/MCP_SERVERS.md`](./docs/MCP_SERVERS.md) · [`docs/TROUBLESHOOTING.md`](./docs/TROUBLESHOOTING.md)

## Security

If you discover a security issue, see `SECURITY.md` for reporting guidance.

## License

MIT License. See `LICENSE`.

## Publishing Notes (Maintainers)

### CLI (PyPI) — tag `vX.Y.Z`

See [`docs/PUBLISHING.md`](./docs/PUBLISHING.md). Pushing `v1.6.0` triggers **PyPI Release** (`.github/workflows/pypi-release.yml`).

### RAYS Studio GUI — tag `studio-vX.Y.Z`

Desktop installers (`.dmg`, `.exe`, `.deb`, `.AppImage`, Arch `.pkg.tar.zst`) are published to **[GitHub Releases](https://github.com/markknoffler/RAYS-CORE-CLI/releases)** via **RAYS Studio Release** (`.github/workflows/studio-release.yml`). See [`docs/STUDIO_RELEASES.md`](./docs/STUDIO_RELEASES.md).

### Build CLI package locally

```bash
python -m pip install --upgrade build twine
python -m build
twine check dist/*
```

### Publish to PyPI

See [`docs/PUBLISHING.md`](./docs/PUBLISHING.md) for the full maintainer checklist (version bump, tag, CI, upload).

```bash
python -m twine upload dist/*
```

### Recommended install command for users

```bash
pipx install rays-core
```

Published package:

- [rays-core on PyPI](https://pypi.org/project/rays-core/)

