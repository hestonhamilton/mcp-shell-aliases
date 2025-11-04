from __future__ import annotations

"""Alias execution helpers with safety guard rails."""

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

from .aliases import Alias
from .config import Config
from .errors import CwdNotAllowedError


@dataclass(slots=True)
class ExecutionResult:
    command: str
    cwd: Path
    exit_code: int | None
    stdout: str
    stderr: str
    truncated_stdout: bool
    truncated_stderr: bool
    timed_out: bool
    dry_run: bool

    def to_payload(self) -> Dict[str, object]:
        return {
            "command": self.command,
            "cwd": str(self.cwd),
            "exitCode": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": {
                "stdout": self.truncated_stdout,
                "stderr": self.truncated_stderr,
            },
            "timedOut": self.timed_out,
            "dryRun": self.dry_run,
        }


async def execute_alias(
    alias: Alias,
    *,
    args: Iterable[str] | str | None,
    config: Config,
    dry_run: bool,
    requested_cwd: Path | None,
    timeout_override: int | None,
) -> ExecutionResult:
    command = _build_command(alias.expansion, args)
    cwd = _resolve_cwd(requested_cwd, config)

    if dry_run:
        return ExecutionResult(
            command=command,
            cwd=cwd,
            exit_code=None,
            stdout=f"Dry run: would execute `{command}` in {cwd}",
            stderr="",
            truncated_stdout=False,
            truncated_stderr=False,
            timed_out=False,
            dry_run=True,
        )

    env = _build_env(os.environ, config, cwd)
    timeout_seconds = timeout_override or config.execution.default_timeout_seconds

    process = await asyncio.create_subprocess_exec(
        "/bin/bash",
        "-lc",
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=env,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
        timed_out = False
    except asyncio.TimeoutError:
        process.kill()
        stdout_bytes, stderr_bytes = await process.communicate()
        timed_out = True

    stdout, stdout_truncated = _decode_and_truncate(stdout_bytes, config.execution.max_stdout_bytes)
    stderr, stderr_truncated = _decode_and_truncate(stderr_bytes, config.execution.max_stderr_bytes)

    exit_code = None if timed_out else process.returncode

    return ExecutionResult(
        command=command,
        cwd=cwd,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        truncated_stdout=stdout_truncated,
        truncated_stderr=stderr_truncated,
        timed_out=timed_out,
        dry_run=False,
    )


def _build_command(expansion: str, args: Iterable[str] | str | None) -> str:
    if args is None:
        return expansion

    if isinstance(args, str):
        arg_suffix = args.strip()
        if arg_suffix:
            return f"{expansion} {arg_suffix}"
        return expansion

    arg_parts: List[str] = []
    for arg in args:
        text = str(arg)
        if text:
            arg_parts.append(text)
    if arg_parts:
        return f"{expansion} {' '.join(arg_parts)}"
    return expansion


def _resolve_cwd(requested: Path | None, config: Config) -> Path:
    if requested is None:
        return config.default_cwd.expanduser().resolve()

    resolved = requested.expanduser().resolve()
    allowed_roots = [root.expanduser().resolve() for root in config.allow_cwd_roots]

    for root in allowed_roots:
        if _is_within(resolved, root):
            return resolved

    raise CwdNotAllowedError(f"Requested cwd {resolved} is outside allowed roots")


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _build_env(base_env: Mapping[str, str], config: Config, cwd: Path) -> Dict[str, str]:
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": base_env.get("LANG", "C.UTF-8"),
        "LC_ALL": base_env.get("LC_ALL", "C.UTF-8"),
        "HOME": str(config.default_cwd.expanduser()),
        "PWD": str(cwd),
    }

    for key in ("LC_CTYPE", "LC_NUMERIC", "LANGUAGE"):
        if key in base_env:
            env[key] = base_env[key]

    return env


def _decode_and_truncate(data: bytes, limit: int) -> Tuple[str, bool]:
    if len(data) <= limit:
        return data.decode("utf-8", errors="replace"), False
    truncated = data[:limit]
    text = truncated.decode("utf-8", errors="replace")
    return text, True


def write_audit_log(
    *,
    config: Config,
    alias: Alias,
    args: Iterable[str] | str | None,
    cwd: Path,
    result: ExecutionResult,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alias": alias.name,
        "safe": alias.safe,
        "args": _format_args(args),
        "cwd": str(cwd),
        "command": result.command,
        "exitCode": result.exit_code,
        "timedOut": result.timed_out,
        "dryRun": result.dry_run,
    }

    payload = json.dumps(_redact(entry), separators=(",", ":"))

    path = config.audit_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


_SECRET_PATTERN = re.compile(r"(?i)(token|secret|password)[^\s]*")


def _format_args(args: Iterable[str] | str | None) -> str:
    if args is None:
        return ""
    if isinstance(args, str):
        return args
    return " ".join(str(arg) for arg in args)


def _redact(entry: Dict[str, object]) -> Dict[str, object]:
    redacted: Dict[str, object] = {}
    for key, value in entry.items():
        if isinstance(value, str):
            redacted[key] = _SECRET_PATTERN.sub("<redacted>", value)
        elif isinstance(value, list):
            redacted[key] = [
                _SECRET_PATTERN.sub("<redacted>", item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted
