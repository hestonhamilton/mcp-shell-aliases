# Gemini Shell Aliases - A tool for creating and managing shell aliases.
# Copyright (C) 2025 Heston Hamilton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Configuration loading for the MCP Shell Alias server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Tuple

import yaml

DEFAULT_CONFIG_FILENAMES = ("config.yaml", "config.yml", "config.json")
ENV_PREFIX = "MCP_SHELL_ALIASES_"


class ConfigError(Exception):
    """Raised when configuration cannot be loaded."""


@dataclass(slots=True)
class ExecutionLimits:
    """Execution guard rails."""

    max_stdout_bytes: int = 10_000
    max_stderr_bytes: int = 10_000
    default_timeout_seconds: int = 20


@dataclass(slots=True)
class Config:
    """Runtime configuration for the server."""

    alias_files: list[Path] = field(default_factory=list)
    allow_patterns: list[str] = field(default_factory=list)
    default_cwd: Path = Path("~").expanduser()
    audit_log_path: Path = Path("~/.local/state/mcp-shell-aliases/audit.log").expanduser()
    enable_hot_reload: bool = True
    execution: ExecutionLimits = field(default_factory=ExecutionLimits)
    allow_cwd_roots: list[Path] = field(default_factory=lambda: [Path("~").expanduser()])
    transport: str = "stdio"
    http_host: str = "127.0.0.1"
    http_port: int = 3921
    http_path: str = "/mcp"

    @classmethod
    def load(
        cls,
        *,
        config_path: Optional[Path] = None,
        cwd: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
        cli_overrides: Optional[Mapping[str, Any]] = None,
    ) -> "Config":
        """Load configuration using precedence: CLI → env → file → defaults."""

        base_dir = Path.cwd() if cwd is None else cwd

        raw_config = _default_dict()

        file_config, resolved_config_path = _load_from_file(config_path=config_path, base_dir=base_dir)
        _merge_dict(raw_config, file_config)
        config_dir = resolved_config_path.parent if resolved_config_path is not None else base_dir

        env_config = _load_from_env(env if env is not None else os.environ)
        for dotted_key, value in env_config.items():
            _apply_override(raw_config, dotted_key, value)

        if cli_overrides:
            for key, value in cli_overrides.items():
                _apply_override(raw_config, key, value)

        return _build_config(raw_config, config_dir=config_dir.resolve())


def _default_dict() -> Dict[str, Any]:
    return {
        "alias_files": [],
        "allow_patterns": [
            r"^ls\b",
            r"^cat\b",
            r"^git\b(?!\s+(push|reset|rebase|clean))",
            r"^grep\b",
            r"^rg\b",
        ],
        "default_cwd": str(Path("~").expanduser()),
        "audit_log_path": str(Path("~/.local/state/mcp-shell-aliases/audit.log").expanduser()),
        "enable_hot_reload": True,
        "execution": {
            "max_stdout_bytes": 10_000,
            "max_stderr_bytes": 10_000,
            "default_timeout_seconds": 20,
        },
        "allow_cwd_roots": [str(Path("~").expanduser())],
        "transport": "stdio",
        "http_host": "127.0.0.1",
        "http_port": 3921,
        "http_path": "/mcp",
    }


def _load_from_file(*, config_path: Optional[Path], base_dir: Path) -> Tuple[Dict[str, Any], Optional[Path]]:
    candidate_paths: Iterable[Path]
    explicit = config_path is not None
    if config_path:
        candidate_paths = (config_path,)
    else:
        candidate_paths = (base_dir / name for name in DEFAULT_CONFIG_FILENAMES)

    for path in candidate_paths:
        expanded = path.expanduser()
        if not expanded.exists():
            continue
        try:
            absolute = expanded.resolve()
            return _read_config_file(expanded), absolute
        except Exception as exc:  # pragma: no cover - sanity guard
            raise ConfigError(f"Failed to read config file {expanded}") from exc

    if explicit:
        missing = config_path.expanduser()
        raise ConfigError(f"Config file {missing} not found")

    return {}, None


def _read_config_file(path: Path) -> Dict[str, Any]:
    """Read YAML or JSON configuration."""
    text = path.read_text(encoding="utf-8")

    if path.suffix.lower() in {".yaml", ".yml", ""}:
        return _ensure_mapping(yaml.safe_load(text) or {}, path)

    if path.suffix.lower() == ".json":
        import json

        return _ensure_mapping(json.loads(text), path)

    raise ConfigError(f"Unsupported config extension: {path.suffix}")


def _ensure_mapping(value: Any, path: Path) -> Dict[str, Any]:
    if not isinstance(value, MutableMapping):
        raise ConfigError(f"Config file {path} must contain a mapping at top level")
    return dict(value)


def _load_from_env(env: Mapping[str, str]) -> Dict[str, Any]:
    results: Dict[str, Any] = {}

    for key, target in _env_key_map().items():
        if key not in env:
            continue
        results[target] = _parse_env_value(target, env[key])

    return results


def _env_key_map() -> Dict[str, str]:
    return {
        f"{ENV_PREFIX}ALIAS_FILES": "alias_files",
        f"{ENV_PREFIX}ALLOW_PATTERNS": "allow_patterns",
        f"{ENV_PREFIX}DEFAULT_CWD": "default_cwd",
        f"{ENV_PREFIX}AUDIT_LOG_PATH": "audit_log_path",
        f"{ENV_PREFIX}ENABLE_HOT_RELOAD": "enable_hot_reload",
        f"{ENV_PREFIX}MAX_STDOUT_BYTES": "execution.max_stdout_bytes",
        f"{ENV_PREFIX}MAX_STDERR_BYTES": "execution.max_stderr_bytes",
        f"{ENV_PREFIX}DEFAULT_TIMEOUT_SECONDS": "execution.default_timeout_seconds",
        f"{ENV_PREFIX}ALLOW_CWD_ROOTS": "allow_cwd_roots",
        f"{ENV_PREFIX}TRANSPORT": "transport",
        f"{ENV_PREFIX}HTTP_HOST": "http_host",
        f"{ENV_PREFIX}HTTP_PORT": "http_port",
        f"{ENV_PREFIX}HTTP_PATH": "http_path",
    }


def _parse_env_value(target: str, raw: str) -> Any:
    if target in {"alias_files", "allow_patterns", "allow_cwd_roots"}:
        return [item for item in raw.split(":") if item]

    if target == "enable_hot_reload":
        return raw.lower() in {"1", "true", "yes", "on"}
    if target in {"transport", "http_host", "http_path", "default_cwd", "audit_log_path"}:
        return raw

    if target.startswith("execution."):
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"Environment value for {target} must be an integer") from exc
    if target == "http_port":
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError("HTTP port must be an integer") from exc

    return raw


def _merge_dict(target: Dict[str, Any], source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        existing = target.get(key)
        if isinstance(value, Mapping) and isinstance(existing, dict):
            _merge_dict(existing, value)
        else:
            target[key] = value


def _apply_override(target: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    current: Dict[str, Any] = target
    for part in parts[:-1]:
        next_value = current.get(part)
        if next_value is None:
            next_value = {}
            current[part] = next_value
        elif not isinstance(next_value, dict):
            raise ConfigError(f"Cannot override nested key {dotted_key}")
        current = next_value
    current[parts[-1]] = value


def _resolve_path(value: str, *, base_dir: Path) -> Path:
    expanded = Path(value).expanduser()
    candidate = expanded if expanded.is_absolute() else base_dir / expanded
    try:
        return candidate.resolve(strict=False)
    except OSError:
        return candidate


def _build_config(raw: Dict[str, Any], *, config_dir: Path) -> Config:
    alias_files = [_resolve_path(p, base_dir=config_dir) for p in raw.get("alias_files", [])]
    if "deny_patterns" in raw:
        raise ConfigError("deny_patterns is no longer supported; remove it and rely on allow_patterns only.")
    default_cwd = Path(raw.get("default_cwd", "~")).expanduser()
    audit_log_path = Path(raw.get("audit_log_path", "~/.local/state/mcp-shell-aliases/audit.log")).expanduser()
    allow_cwd_roots = [Path(p).expanduser() for p in raw.get("allow_cwd_roots", [])]

    execution_dict = raw.get("execution", {})
    execution = ExecutionLimits(
        max_stdout_bytes=int(execution_dict.get("max_stdout_bytes", 10_000)),
        max_stderr_bytes=int(execution_dict.get("max_stderr_bytes", 10_000)),
        default_timeout_seconds=int(execution_dict.get("default_timeout_seconds", 20)),
    )

    transport = str(raw.get("transport", "stdio")).lower()
    http_host = str(raw.get("http_host", "127.0.0.1"))
    http_port = int(raw.get("http_port", 3921))
    http_path = str(raw.get("http_path", "/mcp"))
    if not http_path.startswith("/"):
        http_path = f"/{http_path}"

    return Config(
        alias_files=alias_files,
        allow_patterns=list(raw.get("allow_patterns", [])),
        default_cwd=default_cwd,
        audit_log_path=audit_log_path,
        enable_hot_reload=bool(raw.get("enable_hot_reload", True)),
        execution=execution,
        allow_cwd_roots=allow_cwd_roots or [default_cwd],
        transport=transport,
        http_host=http_host,
        http_port=http_port,
        http_path=http_path,
    )
