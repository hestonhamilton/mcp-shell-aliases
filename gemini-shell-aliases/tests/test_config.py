from __future__ import annotations

from pathlib import Path

import pytest

from mcp_bash_aliases.config import Config, ConfigError


def test_default_config(tmp_path: Path) -> None:
    config = Config.load(cwd=tmp_path)
    assert config.alias_files == []
    assert config.execution.max_stdout_bytes == 10_000
    assert config.enable_hot_reload is True


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
    config = Config.load(cwd=tmp_path)
    assert config.execution.max_stdout_bytes == 2048


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

    overrides = {"execution": {"max_stdout_bytes": 2048}, "default_cwd": str(tmp_path)}
    config = Config.load(config_path=config_path, cli_overrides=overrides)

    assert config.execution.max_stdout_bytes == 2048
    assert config.execution.max_stderr_bytes == 10_000  # untouched default
    assert config.default_cwd == tmp_path


def test_json_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"alias_files": ["/tmp/test_aliases"]}', encoding="utf-8")

    config = Config.load(config_path=config_path)
    assert config.alias_files == [Path("/tmp/test_aliases")]


def test_allow_cwd_roots_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_ALLOW_CWD_ROOTS", "")
    config = Config.load(cwd=tmp_path)
    assert config.allow_cwd_roots == [config.default_cwd]


def test_enable_hot_reload_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_BASH_ALIASES_ENABLE_HOT_RELOAD", "false")
    config = Config.load(cwd=tmp_path)
    assert config.enable_hot_reload is False
