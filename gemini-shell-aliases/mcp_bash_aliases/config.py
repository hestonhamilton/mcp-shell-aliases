"""Configuration loading for the MCP Bash Alias server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

import yaml

DEFAULT_CONFIG_FILENAMES = ("config.yaml", "config.yml", "config.json")
ENV_PREFIX = "MCP_BASH_ALIASES_"


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
    deny_patterns: list[str] = field(default_factory=list)
    default_cwd: Path = Path("~").expanduser()
    audit_log_path: Path = Path("~/.local/state/mcp-bash-aliases/audit.log").expanduser()
    enable_hot_reload: bool = True
    execution: ExecutionLimits = field(default_factory=ExecutionLimits)
    allow_cwd_roots: list[Path] = field(default_factory=lambda: [Path("~").expanduser()])

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

        file_config = _load_from_file(config_path=config_path, base_dir=base_dir)
        _merge_dict(raw_config, file_config)

        env_config = _load_from_env(env if env is not None else os.environ)
        for dotted_key, value in env_config.items():
            _apply_override(raw_config, dotted_key, value)

        if cli_overrides:
            for key, value in cli_overrides.items():
                _apply_override(raw_config, key, value)

        return _build_config(raw_config)


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
        "deny_patterns": [
            r"^rm\b",
            r"^dd\b",
            r"^shutdown\b",
            r"^reboot\b",
            r"^sudo\b",
        ],
        "default_cwd": str(Path("~").expanduser()),
        "audit_log_path": str(Path("~/.local/state/mcp-bash-aliases/audit.log").expanduser()),
        "enable_hot_reload": True,
        "execution": {
            "max_stdout_bytes": 10_000,
            "max_stderr_bytes": 10_000,
            "default_timeout_seconds": 20,
        },
        "allow_cwd_roots": [str(Path("~").expanduser())],
    }


def _load_from_file(*, config_path: Optional[Path], base_dir: Path) -> Dict[str, Any]:
    candidate_paths: Iterable[Path]
    if config_path:
        candidate_paths = (config_path,)
    else:
        candidate_paths = (base_dir / name for name in DEFAULT_CONFIG_FILENAMES)

    for path in candidate_paths:
        expanded = path.expanduser()
        if not expanded.exists():
            continue
        try:
            return _read_config_file(expanded)
        except Exception as exc:  # pragma: no cover - sanity guard
            raise ConfigError(f"Failed to read config file {expanded}") from exc

    return {}


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
        f"{ENV_PREFIX}DENY_PATTERNS": "deny_patterns",
        f"{ENV_PREFIX}DEFAULT_CWD": "default_cwd",
        f"{ENV_PREFIX}AUDIT_LOG_PATH": "audit_log_path",
        f"{ENV_PREFIX}ENABLE_HOT_RELOAD": "enable_hot_reload",
        f"{ENV_PREFIX}MAX_STDOUT_BYTES": "execution.max_stdout_bytes",
        f"{ENV_PREFIX}MAX_STDERR_BYTES": "execution.max_stderr_bytes",
        f"{ENV_PREFIX}DEFAULT_TIMEOUT_SECONDS": "execution.default_timeout_seconds",
        f"{ENV_PREFIX}ALLOW_CWD_ROOTS": "allow_cwd_roots",
    }


def _parse_env_value(target: str, raw: str) -> Any:
    if target in {"alias_files", "allow_patterns", "deny_patterns", "allow_cwd_roots"}:
        return [item for item in raw.split(":") if item]

    if target == "enable_hot_reload":
        return raw.lower() in {"1", "true", "yes", "on"}

    if target.startswith("execution."):
        try:
            return int(raw)
        except ValueError as exc:
            raise ConfigError(f"Environment value for {target} must be an integer") from exc

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


def _build_config(raw: Dict[str, Any]) -> Config:
    alias_files = [Path(p).expanduser() for p in raw.get("alias_files", [])]
    default_cwd = Path(raw.get("default_cwd", "~")).expanduser()
    audit_log_path = Path(raw.get("audit_log_path", "~/.local/state/mcp-bash-aliases/audit.log")).expanduser()
    allow_cwd_roots = [Path(p).expanduser() for p in raw.get("allow_cwd_roots", [])]

    execution_dict = raw.get("execution", {})
    execution = ExecutionLimits(
        max_stdout_bytes=int(execution_dict.get("max_stdout_bytes", 10_000)),
        max_stderr_bytes=int(execution_dict.get("max_stderr_bytes", 10_000)),
        default_timeout_seconds=int(execution_dict.get("default_timeout_seconds", 20)),
    )

    return Config(
        alias_files=alias_files,
        allow_patterns=list(raw.get("allow_patterns", [])),
        deny_patterns=list(raw.get("deny_patterns", [])),
        default_cwd=default_cwd,
        audit_log_path=audit_log_path,
        enable_hot_reload=bool(raw.get("enable_hot_reload", True)),
        execution=execution,
        allow_cwd_roots=allow_cwd_roots or [default_cwd],
    )
