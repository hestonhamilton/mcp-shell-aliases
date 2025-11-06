# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_bash_aliases.config import Config, ConfigError


def test_default_config(tmp_path: Path) -> None:
    config = Config.load(cwd=tmp_path)
    assert config.alias_files == []
    assert config.execution.max_stdout_bytes == 10_000
    assert config.enable_hot_reload is True
    assert config.transport == "stdio"
    assert config.http_host == "127.0.0.1"
    assert config.http_port == 3921
    assert config.http_path == "/mcp"


def test_load_from_file(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        alias_files:
          - /tmp/example_aliases
        execution:
          default_timeout_seconds: 5
        """,
        encoding="utf-8",
    )

    config = Config.load(config_path=config_path)
    assert config.alias_files == [Path("/tmp/example_aliases")]
    assert config.execution.default_timeout_seconds == 5


def test_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_MAX_STDOUT_BYTES", "2048")
    monkeypatch.setenv("MCP_BASH_ALIASES_TRANSPORT", "http")
    monkeypatch.setenv("MCP_BASH_ALIASES_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_BASH_ALIASES_HTTP_PORT", "4000")
    monkeypatch.setenv("MCP_BASH_ALIASES_HTTP_PATH", "api")
    config = Config.load(cwd=tmp_path)
    assert config.execution.max_stdout_bytes == 2048
    assert config.transport == "http"
    assert config.http_host == "0.0.0.0"
    assert config.http_port == 4000
    assert config.http_path == "/api"


def test_invalid_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_MAX_STDOUT_BYTES", "not-an-int")
    with pytest.raises(ConfigError):
        Config.load()


def test_cli_overrides_precedence(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        execution:
          max_stdout_bytes: 4096
        """,
        encoding="utf-8",
    )

    overrides = {
        "execution": {"max_stdout_bytes": 2048},
        "default_cwd": str(tmp_path),
        "transport": "http",
        "http_host": "0.0.0.0",
        "http_port": 4500,
        "http_path": "/custom",
    }
    config = Config.load(config_path=config_path, cli_overrides=overrides)

    assert config.execution.max_stdout_bytes == 2048
    assert config.execution.max_stderr_bytes == 10_000  # untouched default
    assert config.default_cwd == tmp_path
    assert config.transport == "http"
    assert config.http_host == "0.0.0.0"
    assert config.http_port == 4500
    assert config.http_path == "/custom"


def test_json_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"alias_files": ["/tmp/test_aliases"], "http_path": "mcp"}', encoding="utf-8")

    config = Config.load(config_path=config_path)
    assert config.alias_files == [Path("/tmp/test_aliases")]
    assert config.http_path == "/mcp"


def test_alias_files_resolve_relative_to_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    alias_dir = tmp_path / "aliases"
    alias_dir.mkdir()
    alias_file = alias_dir / "aliases"
    alias_file.write_text("alias hi='echo hi'\n", encoding="utf-8")

    config_path = config_dir / "config.yaml"
    config_path.write_text(
        "alias_files:\n  - ../aliases/aliases\n",
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    config = Config.load(config_path=config_path)

    assert config.alias_files == [alias_file]


def test_alias_files_expand_user(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    alias_file = home / ".bash_aliases"
    alias_file.write_text("alias hi='echo hi'\n", encoding="utf-8")

    config_path = tmp_path / "config.yaml"
    config_path.write_text("alias_files:\n  - '~/.bash_aliases'\n", encoding="utf-8")

    config = Config.load(config_path=config_path)

    assert config.alias_files == [alias_file]


def test_allow_cwd_roots_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_ALLOW_CWD_ROOTS", "")
    config = Config.load(cwd=tmp_path)
    assert config.allow_cwd_roots == [config.default_cwd]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        Config.load(config_path=tmp_path / "missing.yaml")


def test_enable_hot_reload_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_ENABLE_HOT_RELOAD", "false")
    config = Config.load(cwd=tmp_path)
    assert config.enable_hot_reload is False
