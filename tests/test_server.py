# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

import json
import signal
from pathlib import Path

import pytest
from fastmcp.client import Client
from fastmcp.exceptions import ToolError

from mcp_shell_aliases.config import Config, ExecutionLimits
from mcp_shell_aliases.server import create_app
from mcp_shell_aliases.server import AliasRuntime, run as run_server


def make_config(tmp_path: Path, alias_file: Path) -> Config:
    return Config(
        alias_files=[alias_file],
        allow_patterns=[r"^echo"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=True,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )


@pytest.fixture
def alias_file(tmp_path: Path) -> Path:
    file_path = tmp_path / "aliases"
    file_path.write_text(
        """
        alias safe='echo hello'
        alias danger='rm -rf /'
        """,
        encoding="utf-8",
    )
    return file_path


@pytest.mark.asyncio
async def test_alias_exec_tool_handles_safe_and_unsafe(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)

    tool = await server.get_tool("alias.exec")

    safe_result = await tool.fn(name="safe", dry_run=True)
    assert safe_result["aliasSafe"] is True
    assert "Dry run" in safe_result["stdout"]

    with pytest.raises(ToolError):
        await tool.fn(name="danger", dry_run=False, confirm=True)


@pytest.mark.asyncio
async def test_alias_exec_unknown_alias(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)

    tool = await server.get_tool("alias.exec")
    with pytest.raises(ToolError):
        await tool.fn(name="missing")


@pytest.mark.asyncio
async def test_alias_exec_timeout_validation(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)
    tool = await server.get_tool("alias.exec")

    with pytest.raises(ToolError):
        await tool.fn(name="safe", dry_run=False, confirm=True, timeout_seconds=0)

    with pytest.raises(ToolError):
        await tool.fn(name="safe", dry_run=False, confirm=True, timeout_seconds=26)


@pytest.mark.asyncio
async def test_alias_exec_disallowed_cwd(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)
    tool = await server.get_tool("alias.exec")

    with pytest.raises(ToolError):
        await tool.fn(name="safe", dry_run=False, confirm=True, cwd=str(tmp_path.parent))


@pytest.mark.asyncio
async def test_alias_catalog_tool_and_resources(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)

    catalog_tool = await server.get_tool("alias.catalog")
    catalog_payload = await catalog_tool.fn()
    assert len(catalog_payload["aliases"]) == 2

    catalog_resource = await server.get_resource("alias://catalog")
    body = await catalog_resource.fn()
    data = json.loads(body)
    assert any(entry["name"] == "safe" for entry in data)

    template = await server.get_resource_template("alias://{alias_name}")
    detail = json.loads(await template.fn(alias_name="safe"))
    assert detail["name"] == "safe"
    assert detail["safe"] is True


@pytest.mark.asyncio
async def test_client_integration(alias_file: Path, tmp_path: Path) -> None:
    config = make_config(tmp_path, alias_file)
    server = create_app(config)

    async with Client(server) as client:
        result = await client.call_tool("alias.exec", {"name": "safe"})
        assert result.structured_content["aliasSafe"] is True

        resource = await client.read_resource("alias://safe")
        detail = json.loads(resource[0].text)
        assert detail["name"] == "safe"


def test_runtime_refresh_disabled(tmp_path: Path) -> None:
    alias_file = tmp_path / "aliases"
    alias_file.write_text("alias safe='echo ok'\n", encoding="utf-8")
    config = Config(
        alias_files=[alias_file],
        allow_patterns=[r"^echo"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )

    runtime = AliasRuntime.build(config)
    aliases = runtime.list_aliases()
    assert aliases[0].name == "safe"


def test_run_prefers_stdio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class DummyServer:
        def __init__(self) -> None:
            self.called_stdio = False

        def run_stdio(self) -> None:
            self.called_stdio = True

    dummy = DummyServer()

    def fake_create_app(config: Config) -> DummyServer:  # type: ignore[override]
        return dummy

    captured_signals: list[int] = []

    def fake_signal(sig: int, handler):  # type: ignore[no-untyped-def]
        captured_signals.append(sig)

    monkeypatch.setattr("mcp_shell_aliases.server.create_app", fake_create_app)
    monkeypatch.setattr("signal.signal", fake_signal)

    config = Config(
        alias_files=[],
        allow_patterns=[r"^echo"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )

    run_server(config)

    assert dummy.called_stdio is True
    assert captured_signals == [signal.SIGINT, signal.SIGTERM]


def test_run_http_transport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class DummyServer:
        def __init__(self) -> None:
            self.called_kwargs: dict[str, object] | None = None

        async def run_http_async(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            self.called_kwargs = kwargs

    dummy = DummyServer()

    def fake_create_app(config: Config) -> DummyServer:  # type: ignore[override]
        return dummy

    captured_signals: list[int] = []

    def fake_signal(sig: int, handler):  # type: ignore[no-untyped-def]
        captured_signals.append(sig)

    async_calls: dict[str, object] = {}

    def fake_asyncio_run(coro):  # type: ignore[no-untyped-def]
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()
        async_calls["called"] = True

    monkeypatch.setattr("mcp_shell_aliases.server.create_app", fake_create_app)
    monkeypatch.setattr("signal.signal", fake_signal)
    monkeypatch.setattr("asyncio.run", fake_asyncio_run)

    config = Config(
        alias_files=[],
        allow_patterns=[r"^echo"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
        transport="http",
        http_host="0.0.0.0",
        http_port=9999,
        http_path="/bridge",
    )

    run_server(config)

    assert async_calls.get("called") is True
    assert dummy.called_kwargs == {
        "show_banner": False,
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9999,
        "path": "/bridge",
    }
    assert captured_signals == [signal.SIGINT, signal.SIGTERM]
