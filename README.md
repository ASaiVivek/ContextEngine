# Context Engine

Agent-agnostic **context engine** for discovering, selecting, and supplying domain knowledge as an agent’s work evolves. MCP is the first integration surface; the core logic stays independent of any single runtime (Claude Code, Codex, IDE agents, custom frameworks).

## Architecture (Phase 1)

```
Agent runtimes ──► Adapters (MCP, runtime hooks) ──► Context Engine ──► Knowledge (Markdown + catalog)
```

| Component | Responsibility |
|-----------|----------------|
| **Resolver** | What is relevant? |
| **Controller** | What should happen now? (stub → Phase D) |
| **Ledger** | What was supplied? |
| **Policy** | How much detail? (budget hooks on requests) |

The engine decides *what* and *why*; adapters decide *how* and *when* delivery is allowed.

## Repository layout

```
knowledge/           # Versioned Markdown + catalog.yaml
src/context_engine/  # Core API and adapters
tests/               # Deterministic engine tests
experiments/         # Phase E tasks, configs, results
docs/                # Phase notes (start with phase-a.md)
```

## Core API

```python
from context_engine import ContextEngine
from context_engine.models import GetRequest, ResolveRequest

engine = ContextEngine()
candidates = engine.resolve(ResolveRequest(
    session_id="run-1",
    task_description="Add idempotent payment retries",
    domain="payments",
))
items = engine.get(GetRequest(session_id="run-1", item_ids=["payments/idempotency"]))
```

See `src/context_engine/models.py` for full request/response types.

## Quick start

```bash
python3 -m pip install -e ".[dev]"
pytest
python3 -m context_engine.adapters.mcp.server
```

MCP tools: `resolve_context`, `get_context`.

## Implementation phases

1. **Phase A** — Validate agent/MCP integration (`docs/phase-a.md`)
2. **Phase B** — Core engine + tests (in progress)
3. **Phase C** — MCP hardening + one real client
4. **Phase D** — Dynamic delivery via a runtime adapter
5. **Phase E** — Compare baseline vs upfront vs dynamic context

## Deliberately out of scope (Phase 1)

Hosted SaaS, vector DB (unless keyword retrieval fails), knowledge graph, full multi-agent support, opaque context removal, autonomous LLM controller, enterprise policy.

## License

MIT
