# Context Engine

ContextEngine is a local runtime harness that supplies domain knowledge while an agent works. It is not a hosted platform, it does not own a team's knowledge, and it does not replace Claude Code, Codex, or another coding agent.

The team brings versioned Markdown and chooses how to expose it. The engine decides which documents are relevant and records what it selected and returned. An adapter carries that result to a particular agent. MCP is the first adapter.

## Architecture

```
Agent runtimes ──► Adapters (MCP today; runtime hooks later) ──► Context Engine ──► Knowledge (Markdown + catalog)
```

| Component | Responsibility |
|-----------|----------------|
| **Resolver** | Rank catalog items for a task with deterministic, explainable scores. |
| **Controller** | Call the resolver. It does not yet watch a live agent run. |
| **Ledger** | Per session: what was selected, returned, and reported used by the host. |
| **Budget** | Trim results with `max_items` and `max_tokens`. |

Returned counts mean the engine handed a document to the caller. Reported use is recorded only when the host sends that signal. The engine does not read an agent's context window.

## Repository layout

```
knowledge/           # catalog.yaml and versioned Markdown
src/context_engine/  # core API, resolver, ledger, MCP adapter
tests/               # 30 passing tests, including a real MCP client
experiments/         # Phase E tasks, configs, results (not started)
docs/phase-a.md      # Host-agent integration checklist
```

## Core API

```python
from context_engine import ContextEngine
from context_engine.models import GetRequest, ResolveRequest

engine = ContextEngine()
resolved = engine.resolve(ResolveRequest(
    session_id="run-1",
    task_description="Add idempotent payment retries",
    domain="payments",
))
items = engine.get(GetRequest(session_id="run-1", item_ids=["payments/idempotency"]))
status = engine.get_status("run-1")
```

`resolve` marks matching items **selected**. `get` marks them **returned** and lists unknown ids on `missing_item_ids`. Repeating the same session, item, and version records a duplicate skip. See `src/context_engine/models.py`.

## MCP tools

Run the stdio server:

```bash
python3 -m pip install -e ".[dev]"
python3 -m context_engine.adapters.mcp
```

`context-engine-mcp` is the same server after install.

| Tool | Returns |
|------|---------|
| `resolve_context` | Ranked candidates, versions, reasons, and status (`matched`, `no_match`, or `domain_empty`). |
| `get_context` | Markdown for the requested ids, plus `missing_item_ids`. |
| `get_session_status` | Ledger totals for that session only. |
| `record_context_usage` | A host-reported use signal. |

Empty relevance is a successful structured response. Blank session ids, empty queries, a bad `domain_filter`, and empty `item_ids` are tool errors and do not change the ledger.

## Tests

**30 tests passing.**

```bash
pytest
```

The MCP tests use the official `ClientSession` over an in-memory connection and a stdio subprocess. They check schemas, errors, empty outcomes, and ledger behavior across repeated calls.

## Progress

| Milestone | State |
|-----------|--------|
| Phase B — agent-independent core: models, catalog, ranking, budgets, empty outcomes | Done |
| Lifecycle ledger — selected, returned, host-reported use, dedupe, versions, sessions | Done |
| Phase C — MCP tools, structured responses, errors, official client | Done |
| Phase A — one real coding agent calling these tools mid-task, with host limits written down | Next |
| Phase D — runtime adapter that supplies more knowledge as a task changes | After Phase A |
| Phase E — baseline vs upfront vs dynamic comparison | Not started |

## Next milestone

Connect one real agent (Claude Code or Codex) to the four MCP tools during a multi-step task. Record which events the host exposes and when context can actually be delivered. Phase D starts from that evidence. See `docs/phase-a.md`.

## Out of scope for this phase

Hosted SaaS, a vector database, a knowledge graph, support for every agent, removing context from an opaque conversation, an autonomous LLM controller, and enterprise policy enforcement.

## License

MIT
