# Copyright (C) 2025 Heston Hamilton

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_shell_aliases.config import Config, ConfigError


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
    monkeypatch.setenv("MCP_SHELL_ALIASES_MAX_STDOUT_BYTES", "2048")
    monkeypatch.setenv("MCP_SHELL_ALIASES_TRANSPORT", "http")
    monkeypatch.setenv("MCP_SHELL_ALIASES_HTTP_HOST", "0.0.0.0")
    monkeypatch.setenv("MCP_SHELL_ALIASES_HTTP_PORT", "4000")
    monkeypatch.setenv("MCP_SHELL_ALIASES_HTTP_PATH", "api")
    config = Config.load(cwd=tmp_path)
    assert config.execution.max_stdout_bytes == 2048
    assert config.transport == "http"
    assert config.http_host == "0.0.0.0"
    assert config.http_port == 4000
    assert config.http_path == "/api"


def test_invalid_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_SHELL_ALIASES_MAX_STDOUT_BYTES", "not-an-int")
    with pytest.raises(ConfigError):
        Config.load()


def test_invalid_http_port_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_SHELL_ALIASES_HTTP_PORT", "not-an-int")
    with pytest.raises(ConfigError, match="HTTP port must be an integer"):
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


def test_unsupported_config_extension_raises(tmp_path: Path) -> None:
    bad = tmp_path / "config.txt"
    bad.write_text("alias_files: []\n", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        Config.load(config_path=bad)
    # The loader wraps underlying errors; verify root cause message
    cause = exc.value.__cause__
    assert cause is not None and "Unsupported config extension" in str(cause)


def test_config_top_level_must_be_mapping(tmp_path: Path) -> None:
    bad_json = tmp_path / "config.json"
    bad_json.write_text('["not", "a", "mapping"]', encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        Config.load(config_path=bad_json)
    cause = exc.value.__cause__
    assert cause is not None and "must contain a mapping" in str(cause)


def test_apply_override_errors_when_overwriting_non_mapping() -> None:
    from mcp_shell_aliases.config import _apply_override

    target: dict[str, object] = {"execution": 1}
    with pytest.raises(ConfigError, match="Cannot override nested key execution.max_stdout_bytes"):
        _apply_override(target, "execution.max_stdout_bytes", 10)


def test_resolve_path_handles_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mcp_shell_aliases.config import _resolve_path
    # Monkeypatch Path.resolve to raise OSError
    class Boom(Exception):
        pass

    def explode(self, strict=False):  # type: ignore[no-untyped-def]
        raise OSError("boom")

    monkeypatch.setattr(Path, "resolve", explode, raising=True)
    # Should return candidate without raising
    p = _resolve_path("relative/file.txt", base_dir=tmp_path)
    assert str(p).endswith("relative/file.txt")


def test_parse_env_value_fallthrough_returns_raw() -> None:
    from mcp_shell_aliases.config import _parse_env_value

    assert _parse_env_value("other.key", "rawval") == "rawval"


def test_apply_override_creates_nested_dict() -> None:
    from mcp_shell_aliases.config import _apply_override

    target: dict[str, object] = {}
    _apply_override(target, "a.b", 1)
    assert target == {"a": {"b": 1}}


def test_deny_patterns_config_raises(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("deny_patterns:\n  - '^rm'\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="deny_patterns is no longer supported"):
        Config.load(config_path=config_path)


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
    monkeypatch.setenv("MCP_SHELL_ALIASES_ALLOW_CWD_ROOTS", "")
    config = Config.load(cwd=tmp_path)
    assert config.allow_cwd_roots == [config.default_cwd]


def test_missing_explicit_config_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        Config.load(config_path=tmp_path / "missing.yaml")


def test_enable_hot_reload_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MCP_SHELL_ALIASES_ENABLE_HOT_RELOAD", "false")
    config = Config.load(cwd=tmp_path)
    assert config.enable_hot_reload is False
