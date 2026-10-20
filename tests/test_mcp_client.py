"""Integration tests against the official MCP ClientSession."""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.memory import create_connected_server_and_client_session

from context_engine.api import ContextEngine
from context_engine.adapters.mcp.server import build_server
from context_engine.models import (
    ContextEngineStatus,
    GetResponse,
    ResolveResponse,
    ResolveStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = REPO_ROOT / "knowledge"


def _text(result) -> str:
    parts = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts)


def test_tool_schemas_expose_session_and_structured_output() -> None:
    async def body() -> None:
        engine = ContextEngine(knowledge_root=KNOWLEDGE)
        async with create_connected_server_and_client_session(build_server(engine)) as client:
            listed = await client.list_tools()
            tools = {tool.name: tool for tool in listed.tools}
            assert {"resolve_context", "get_context", "get_session_status", "record_context_usage"} <= set(
                tools
            )

            resolve = tools["resolve_context"]
            assert "session_id" in resolve.inputSchema["required"]
            assert "task_description" in resolve.inputSchema["required"]
            assert resolve.outputSchema is not None
            assert "status" in resolve.outputSchema["properties"]
            assert "candidates" in resolve.outputSchema["properties"]

            get_tool = tools["get_context"]
            assert "session_id" in get_tool.inputSchema["required"]
            assert "item_ids" in get_tool.inputSchema["required"]
            assert get_tool.outputSchema is not None
            assert "missing_item_ids" in get_tool.outputSchema["properties"]

            status = tools["get_session_status"]
            assert status.outputSchema is not None
            assert "observation_scope" in status.outputSchema["properties"]
            assert "totals" in status.outputSchema["properties"]

    anyio.run(body)


def test_client_resolve_and_get_keep_session_ledger() -> None:
    async def body() -> None:
        engine = ContextEngine(knowledge_root=KNOWLEDGE)
        async with create_connected_server_and_client_session(build_server(engine)) as client:
            first = await client.call_tool(
                "resolve_context",
                {
                    "session_id": "mcp-session",
                    "task_description": "Implement idempotent payment retries",
                    "domain": "payments",
                    "domain_filter": "restrict",
                    "include_content": False,
                },
            )
            assert first.isError is False
            resolved = ResolveResponse.model_validate(first.structuredContent)
            assert resolved.session_id == "mcp-session"
            assert resolved.status == ResolveStatus.MATCHED
            assert resolved.candidates
            item_id = resolved.candidates[0].item_id

            fetched = await client.call_tool(
                "get_context",
                {"session_id": "mcp-session", "item_ids": [item_id, item_id]},
            )
            assert fetched.isError is False
            got = GetResponse.model_validate(fetched.structuredContent)
            assert got.session_id == "mcp-session"
            assert [item.item_id for item in got.items] == [item_id, item_id]
            assert got.items[0].content
            assert got.items[0].version

            again = await client.call_tool(
                "get_context",
                {"session_id": "mcp-session", "item_ids": [item_id]},
            )
            assert again.isError is False

            await client.call_tool(
                "resolve_context",
                {
                    "session_id": "mcp-session",
                    "task_description": "Implement idempotent payment retries",
                    "domain": "payments",
                    "include_content": False,
                },
            )

            status_result = await client.call_tool(
                "get_session_status",
                {"session_id": "mcp-session"},
            )
            assert status_result.isError is False
            status = ContextEngineStatus.model_validate(status_result.structuredContent)
            assert status.session_id == "mcp-session"
            assert status.totals.selected >= 1
            assert status.totals.returned == 1
            assert status.totals.duplicate_return_skips >= 1
            assert status.totals.duplicate_select_skips >= 1
            assert "context window" in status.observation_scope

            other = await client.call_tool(
                "get_session_status",
                {"session_id": "other-session"},
            )
            other_status = ContextEngineStatus.model_validate(other.structuredContent)
            assert other_status.totals.returned == 0
            assert other_status.totals.selected == 0

    anyio.run(body)


def test_empty_outcome_is_structured_not_an_error() -> None:
    async def body() -> None:
        engine = ContextEngine(knowledge_root=KNOWLEDGE)
        async with create_connected_server_and_client_session(build_server(engine)) as client:
            result = await client.call_tool(
                "resolve_context",
                {
                    "session_id": "empty-session",
                    "task_description": "xyzzy plugh unrelated",
                },
            )
            assert result.isError is False
            parsed = ResolveResponse.model_validate(result.structuredContent)
            assert parsed.status == ResolveStatus.NO_MATCH
            assert parsed.candidates == []
            assert parsed.message

            missing = await client.call_tool(
                "get_context",
                {"session_id": "empty-session", "item_ids": ["does/not-exist"]},
            )
            assert missing.isError is False
            got = GetResponse.model_validate(missing.structuredContent)
            assert got.items == []
            assert got.missing_item_ids == ["does/not-exist"]

    anyio.run(body)


def test_invalid_calls_return_tool_errors() -> None:
    async def body() -> None:
        engine = ContextEngine(knowledge_root=KNOWLEDGE)
        async with create_connected_server_and_client_session(build_server(engine)) as client:
            blank = await client.call_tool(
                "resolve_context",
                {"session_id": "   ", "task_description": "payment retry"},
            )
            assert blank.isError is True
            assert "session_id" in _text(blank)

            missing_arg = await client.call_tool(
                "resolve_context",
                {"session_id": "s"},
            )
            assert missing_arg.isError is True

            bad_filter = await client.call_tool(
                "resolve_context",
                {
                    "session_id": "s",
                    "task_description": "payment retry",
                    "domain_filter": "only",
                },
            )
            assert bad_filter.isError is True
            assert "domain_filter" in _text(bad_filter)

            empty_ids = await client.call_tool(
                "get_context",
                {"session_id": "s", "item_ids": []},
            )
            assert empty_ids.isError is True

            status = engine.get_status("s")
            assert status.totals.selected == 0
            assert status.totals.returned == 0

    anyio.run(body)


def test_stdio_client_round_trip() -> None:
    async def body() -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "context_engine.adapters.mcp"],
            cwd=str(REPO_ROOT),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                resolved = await client.call_tool(
                    "resolve_context",
                    {
                        "session_id": "stdio-session",
                        "task_description": "ECS rolling deployment",
                        "domain": "infrastructure",
                        "include_content": False,
                    },
                )
                assert resolved.isError is False
                parsed = ResolveResponse.model_validate(resolved.structuredContent)
                assert parsed.status == ResolveStatus.MATCHED
                item_id = parsed.candidates[0].item_id

                fetched = await client.call_tool(
                    "get_context",
                    {"session_id": "stdio-session", "item_ids": [item_id]},
                )
                got = GetResponse.model_validate(fetched.structuredContent)
                assert got.items[0].item_id == item_id
                assert "ECS" in (got.items[0].content or "")

                second = await client.call_tool(
                    "get_context",
                    {"session_id": "stdio-session", "item_ids": [item_id]},
                )
                assert second.isError is False

                status_result = await client.call_tool(
                    "get_session_status",
                    {"session_id": "stdio-session"},
                )
                status = ContextEngineStatus.model_validate(status_result.structuredContent)
                assert status.totals.selected >= 1
                assert status.totals.returned == 1
                assert status.totals.duplicate_return_skips == 1
                assert status.totals.reported_used == 0

                reported = await client.call_tool(
                    "record_context_usage",
                    {
                        "session_id": "stdio-session",
                        "item_id": item_id,
                        "version": got.items[0].version,
                        "detail": "host_callback",
                    },
                )
                assert reported.isError is False
                after = await client.call_tool(
                    "get_session_status",
                    {"session_id": "stdio-session"},
                )
                after_status = ContextEngineStatus.model_validate(after.structuredContent)
                assert after_status.totals.reported_used == 1

    anyio.run(body)
