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

