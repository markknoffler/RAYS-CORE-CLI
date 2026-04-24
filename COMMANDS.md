# RAYS — Commands & Flags Reference

## CLI Usage

```
rays                              # Start RAYS in the current working directory
rays -c /path/to/codebase         # Start RAYS in a specific codebase directory
rays --codebase_path /path        # Same as above (long form)
rays --config /path/to/config     # Use a custom config file
rays --reindex                    # Force re-index the codebase on startup
rays --rebuild_db                 # Force rebuild the vector database on startup
rays --auto_approve               # Auto-approve all permission slips
rays --conversation_id <id>       # Resume or name a specific conversation session
```

## Slash Commands (in-conversation)

| Command             | Description                                          |
| ------------------- | ---------------------------------------------------- |
| `/help`             | Show all available commands                          |
| `/exit`             | Exit RAYS                                            |
| `/model <name>`     | Switch to a different model (e.g. `/model qwen3:8b`) |
| `/mode auto`        | Switch to autonomous execution (no confirmations)    |
| `/mode ask`         | Switch to ask-permission mode for terminal commands  |
| `/clear`            | Clear the terminal screen                            |
| `/done`             | Submit a multi-line paste                            |

## Execution Modes

| Mode          | Behavior                                                  |
| ------------- | --------------------------------------------------------- |
| `ask`         | RAYS asks for permission before each terminal command      |
| `autonomous`  | RAYS executes all terminal commands without confirmation   |

You can set the default mode in `config.yaml` under `execution_mode`, or toggle it during a conversation with `/mode auto` or `/mode ask`.

## Multi-line Input

For long prompts or pasting large blocks of text:
1. Paste your text — if more than 5 lines, RAYS shows "N lines pasted"
2. Or end a line with `\` to continue on the next line, then use `/done` to submit

## Config File (`config.yaml`)

Key settings:
- `llm.model` — Default LLM model
- `llm.provider` — `ollama` or `gemini`
- `embedding.model` — Embedding model
- `execution_mode` — `ask` or `autonomous`
- `available_models` — List of models shown in the model selector
