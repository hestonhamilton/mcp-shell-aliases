# Copyright (C) 2025 Heston Hamilton
from __future__ import annotations
from pathlib import Path

import pytest

from mcp_shell_aliases.aliases import Alias
from mcp_shell_aliases.config import Config, ExecutionLimits
from mcp_shell_aliases.errors import CwdNotAllowedError
from mcp_shell_aliases.execution import ExecutionResult, execute_alias, write_audit_log
from mcp_shell_aliases.execution import _build_command, _resolve_cwd, _is_within, _build_env, _redact


def make_config(tmp_path: Path) -> Config:
    return Config(
        alias_files=[],
        allow_patterns=[r"^echo"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )


@pytest.mark.asyncio
async def test_execute_dry_run(tmp_path: Path) -> None:
    alias = Alias(name="greet", expansion="echo hello", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args="world",
        config=config,
        dry_run=True,
        requested_cwd=None,
        timeout_override=None,
    )

    assert isinstance(result, ExecutionResult)
    assert result.dry_run is True
    assert "Dry run" in result.stdout


@pytest.mark.asyncio
async def test_execute_runs_command(tmp_path: Path) -> None:
    alias = Alias(name="greet", expansion="echo hello", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args=None,
        config=config,
        dry_run=False,
        requested_cwd=None,
        timeout_override=None,
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"


@pytest.mark.asyncio
async def test_disallows_outside_cwd(tmp_path: Path) -> None:
    alias = Alias(name="greet", expansion="echo hello", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    with pytest.raises(CwdNotAllowedError):
        await execute_alias(
            alias,
            args=None,
            config=config,
            dry_run=False,
            requested_cwd=Path("/"),
            timeout_override=None,
        )


@pytest.mark.asyncio
async def test_audit_log_preserves_args_string(tmp_path: Path) -> None:
    alias = Alias(name="greet", expansion="echo hello", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args="world",
        config=config,
        dry_run=True,
        requested_cwd=None,
        timeout_override=None,
    )

    write_audit_log(
        config=config,
        alias=alias,
        args="world",
        cwd=result.cwd,
        result=result,
    )

    log_text = config.audit_log_path.read_text(encoding="utf-8")
    assert '"args":"world"' in log_text


@pytest.mark.asyncio
async def test_execute_times_out(tmp_path: Path) -> None:
    alias = Alias(
        name="slow",
        expansion="python3 -c 'import time; time.sleep(2)'",
        safe=True,
        source_file=tmp_path / "aliases",
    )
    config = Config(
        alias_files=[],
        allow_patterns=[r"^python3"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )

    result = await execute_alias(
        alias,
        args=None,
        config=config,
        dry_run=False,
        requested_cwd=None,
        timeout_override=1,
    )

    assert result.timed_out is True
    assert result.exit_code is None


@pytest.mark.asyncio
async def test_execute_with_iterable_args(tmp_path: Path) -> None:
    alias = Alias(
        name="say",
        expansion="echo",
        safe=True,
        source_file=tmp_path / "aliases",
    )
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args=["hello", "world"],
        config=config,
        dry_run=False,
        requested_cwd=None,
        timeout_override=None,
    )

    assert result.exit_code == 0
    assert result.command.endswith("hello world")
    assert "hello world" in result.stdout


def test_build_command_string_arg_whitespace() -> None:
    assert _build_command("echo hi", "   ") == "echo hi"


def test_build_command_iterable_empty() -> None:
    assert _build_command("echo hi", []) == "echo hi"


def test_is_within_true_and_false(tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    assert _is_within(inner, tmp_path) is True
    assert _is_within(tmp_path, inner) is False


def test_resolve_cwd_allows_within_root(tmp_path: Path) -> None:
    inner = (tmp_path / "inner").resolve()
    inner.mkdir()
    cfg = make_config(tmp_path)
    path = _resolve_cwd(inner, cfg)
    assert path == inner


def test_build_env_passes_through_locale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    base = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "LC_CTYPE": "en_US.UTF-8"}
    cfg = make_config(tmp_path)
    env = _build_env(base, cfg, tmp_path)
    assert env["LC_CTYPE"] == "en_US.UTF-8"


def test_redact_list_items() -> None:
    data = {"items": ["token=abc", "ok", 5]}
    out = _redact(data)
    assert out["items"][0] == "<redacted>"


@pytest.mark.asyncio
async def test_audit_log_serializes_iterable_args(tmp_path: Path) -> None:
    alias = Alias(name="greet", expansion="echo hello", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args=["earth"],
        config=config,
        dry_run=True,
        requested_cwd=None,
        timeout_override=None,
    )

    write_audit_log(
        config=config,
        alias=alias,
        args=["earth"],
        cwd=result.cwd,
        result=result,
    )

    log_text = config.audit_log_path.read_text(encoding="utf-8")
    assert '"args":"earth"' in log_text


@pytest.mark.asyncio
async def test_audit_log_redacts_secrets(tmp_path: Path) -> None:
    alias = Alias(name="run", expansion="echo ok", safe=True, source_file=tmp_path / "aliases")
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args="token=abcd password=hunter2 SECRET_key=xyz",
        config=config,
        dry_run=True,
        requested_cwd=None,
        timeout_override=None,
    )

    write_audit_log(
        config=config,
        alias=alias,
        args="token=abcd password=hunter2 SECRET_key=xyz",
        cwd=result.cwd,
        result=result,
    )

    text = config.audit_log_path.read_text(encoding="utf-8")
    assert "<redacted>" in text
    assert "hunter2" not in text
    assert "abcd" not in text


@pytest.mark.asyncio
async def test_stdout_and_stderr_truncation(tmp_path: Path) -> None:
    # Produce large stdout and stderr via Python
    big = "x" * 5000
    script = (
        "python3 - <<'PY'\n"
        "import sys\n"
        f"sys.stdout.write('{big}')\n"
        f"sys.stderr.write('{big}')\n"
        "PY"
    )

    alias = Alias(name="spam", expansion=script, safe=True, source_file=tmp_path / "aliases")
    config = Config(
        alias_files=[],
        allow_patterns=[r"^python3"],
        default_cwd=tmp_path,
        audit_log_path=tmp_path / "audit.log",
        enable_hot_reload=False,
        execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=800, default_timeout_seconds=5),
        allow_cwd_roots=[tmp_path],
    )

    result = await execute_alias(
        alias,
        args=None,
        config=config,
        dry_run=False,
        requested_cwd=None,
        timeout_override=None,
    )

    assert result.truncated_stdout is True
    assert result.truncated_stderr is True
    assert len(result.stdout) == 1000
    assert len(result.stderr) == 800


@pytest.mark.asyncio
async def test_env_and_cwd_are_set(tmp_path: Path) -> None:
    # Echo HOME and PWD from the sandboxed process
    alias = Alias(
        name="envcheck",
        expansion="bash -lc 'echo \"$HOME::$PWD\"'",
        safe=True,
        source_file=tmp_path / "aliases",
    )
    config = make_config(tmp_path)

    result = await execute_alias(
        alias,
        args=None,
        config=config,
        dry_run=False,
        requested_cwd=None,
        timeout_override=None,
    )

    expected_home = str(config.default_cwd)
    expected_pwd = str(config.default_cwd)
    assert result.stdout.strip() == f"{expected_home}::{expected_pwd}"
