# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from mcp_shell_aliases import cli
from mcp_shell_aliases.config import Config, ExecutionLimits


def test_build_cli_overrides(tmp_path: Path) -> None:
    args = cli.parse_args(
        [
            "--alias-file",
            str(tmp_path / "aliases1"),
            "--allow-pattern",
            r"^echo",
            "--default-cwd",
            str(tmp_path),
            "--no-hot-reload",
            "--max-stdout-bytes",
            "2048",
            "--max-stderr-bytes",
            "1024",
            "--timeout",
            "15",
            "--allow-cwd-root",
            str(tmp_path / "workspace"),
            "--transport",
            "http",
            "--http-host",
            "0.0.0.0",
            "--http-port",
            "4321",
            "--http-path",
            "alt",
        ]
    )

    overrides = cli.build_cli_overrides(args)
    assert overrides["alias_files"] == [str(tmp_path / "aliases1")]
    assert overrides["allow_patterns"] == [r"^echo"]
    assert overrides["default_cwd"] == str(tmp_path)
    assert overrides["enable_hot_reload"] is False
    assert overrides["execution"]["max_stdout_bytes"] == 2048
    assert overrides["execution"]["max_stderr_bytes"] == 1024
    assert overrides["execution"]["default_timeout_seconds"] == 15
    assert overrides["allow_cwd_roots"] == [str(tmp_path / "workspace")]
    assert overrides["transport"] == "http"
    assert overrides["http_host"] == "0.0.0.0"
    assert overrides["http_port"] == 4321
    assert overrides["http_path"] == "alt"


def test_main_invokes_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("alias_files: []\n", encoding="utf-8")

    captured: dict[str, Config] = {}

    def fake_run(config: Config) -> None:
        captured["config"] = config

    def fake_load(cls, *, config_path: Path | None, cli_overrides, **_: object) -> Config:  # type: ignore[unused-argument]
        assert config_path == cfg_path
        return Config(
            alias_files=[],
            allow_patterns=[r"^echo"],
            default_cwd=tmp_path,
            audit_log_path=tmp_path / "audit.log",
            enable_hot_reload=False,
            execution=ExecutionLimits(max_stdout_bytes=1000, max_stderr_bytes=1000, default_timeout_seconds=5),
            allow_cwd_roots=[tmp_path],
        )

    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(cli.Config, "load", classmethod(fake_load))

    cli.main(["--config", str(cfg_path), "--verbose"])

    assert "config" in captured
    assert captured["config"].default_cwd == tmp_path


def test_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {}

    def fake_main(argv: list[str] | None = None) -> None:
        called["argv"] = argv

    monkeypatch.setattr(cli, "main", fake_main)

    runpy.run_module("mcp_shell_aliases", run_name="__main__")

    assert "argv" in called


def test_cli_module_entrypoint_calls_main(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure argparse doesn't see pytest's argv
    import sys

    monkeypatch.setattr(sys, "argv", ["prog"])  # no args

    # Ensure a clean import state for runpy to avoid RuntimeWarning
    sys.modules.pop("mcp_shell_aliases.cli", None)

    # Stub Config.load and server.run to avoid side effects
    called = {"run": False, "loaded": False}

    def fake_load(cls, *, config_path=None, cli_overrides=None, **kwargs):  # type: ignore[no-untyped-def]
        called["loaded"] = True
        from mcp_shell_aliases.config import Config, ExecutionLimits

        return Config(
            alias_files=[],
            allow_patterns=[r"^echo"],
            default_cwd=Path.cwd(),
            audit_log_path=Path.cwd() / "audit.log",
            enable_hot_reload=False,
            execution=ExecutionLimits(),
            allow_cwd_roots=[Path.cwd()],
        )

    def fake_run(_config):  # type: ignore[no-untyped-def]
        called["run"] = True

    monkeypatch.setattr("mcp_shell_aliases.config.Config.load", classmethod(fake_load))
    monkeypatch.setattr("mcp_shell_aliases.server.run", fake_run)

    runpy.run_module("mcp_shell_aliases.cli", run_name="__main__")

    assert called["loaded"] is True and called["run"] is True
