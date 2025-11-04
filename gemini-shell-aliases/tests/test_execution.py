from __future__ import annotations
from pathlib import Path

import pytest

from mcp_bash_aliases.aliases import Alias
from mcp_bash_aliases.config import Config, ExecutionLimits
from mcp_bash_aliases.errors import CwdNotAllowedError
from mcp_bash_aliases.execution import ExecutionResult, execute_alias, write_audit_log


def make_config(tmp_path: Path) -> Config:
    return Config(
        alias_files=[],
        allow_patterns=[r"^echo"],
        deny_patterns=[r"^rm"],
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
