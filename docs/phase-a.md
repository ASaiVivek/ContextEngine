# Phase A — Validate integration

## Development environment (this repo)

| Item | Value |
|------|--------|
| OS | Linux (Cloud Agent VM; local dev may be macOS/Windows) |
| Python | 3.11+ (`python3 --version`) |
| Package manager | pip + `pyproject.toml` (uv optional) |

### Bootstrap

```bash
cd /path/to/ContextEngine
python3 -m pip install -e ".[dev]"
pytest
```

### Run the MCP server (stdio)

```bash
python3 -m context_engine.adapters.mcp.server
# or after install:
context-engine-mcp
```

For local inspection with the MCP CLI (requires `mcp[cli]`):

```bash
pip install "mcp[cli]<2"
mcp dev src/context_engine/adapters/mcp/server.py
```

## Checklist (Days 1–2)

- [ ] Confirm MCP transport supported by target agent (stdio vs SSE)
- [ ] List observable runtime events (tool calls, errors, session lifecycle)
- [ ] Verify when `resolve_context` / `get_context` can be invoked mid-task
- [ ] Document host-specific limitations (context window control, injection paths)

## Agent test matrix

Fill in after first connection attempt:

| Agent | MCP client? | Mid-task tools? | Notes |
|-------|-------------|-----------------|-------|
| Claude Code | TBD | TBD | Primary test target |
| Codex | TBD | TBD | |
| IDE agents | TBD | TBD | |
