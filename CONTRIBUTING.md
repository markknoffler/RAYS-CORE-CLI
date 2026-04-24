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
python -m pip install -e .
```

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

- Run local install in editable mode.
- Start `rays` and verify startup flow.
- Validate at least one provider path (Ollama or Gemini).
- Verify `/chat`, `/mode`, and one edit pipeline prompt.

## Commit Message Style

Use concise, intent-first messages:

- `feat: add OpenAI chat/embedding support in AIClient`
- `fix: handle missing provider keys with clear fallback`
- `docs: expand README with pipeline and install guidance`

## Good First Contributions

- Improve prompt templates and fallback behavior.
- Add provider-specific troubleshooting docs.
- Strengthen error messages and diagnostics.
- Add tests around task analysis and pipeline routing.

