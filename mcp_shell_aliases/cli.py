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

"""Command-line entry point for the MCP Shell Aliases server."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import Config
from .server import run

logger = logging.getLogger(__name__)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the MCP Shell Aliases server.")
    parser.add_argument("--config", type=Path, help="Path to configuration file.")
    parser.add_argument(
        "--alias-file",
        action="append",
        dest="alias_files",
        default=None,
        help="Additional alias file to load (can be passed multiple times).",
    )
    parser.add_argument(
        "--allow-pattern",
        action="append",
        dest="allow_patterns",
        default=None,
        help="Regex pattern that marks an alias expansion as safe.",
    )
    parser.add_argument(
        "--default-cwd",
        type=str,
        help="Default working directory for alias execution.",
    )
    parser.add_argument(
        "--hot-reload",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable hot reload of alias files.",
    )
    parser.add_argument(
        "--max-stdout-bytes",
        type=int,
        dest="max_stdout_bytes",
        help="Maximum stdout bytes before truncation.",
    )
    parser.add_argument(
        "--max-stderr-bytes",
        type=int,
        dest="max_stderr_bytes",
        help="Maximum stderr bytes before truncation.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        dest="default_timeout_seconds",
        help="Default execution timeout in seconds.",
    )
    parser.add_argument(
        "--allow-cwd-root",
        action="append",
        dest="allow_cwd_roots",
        default=None,
        help="Root directory allowed for alias execution (can be passed multiple times).",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse", "streamable-http"],
        help="Transport to run the server with (default: stdio).",
    )
    parser.add_argument("--http-host", help="Host to bind when using HTTP-based transports.")
    parser.add_argument("--http-port", type=int, help="Port to bind when using HTTP-based transports.")
    parser.add_argument(
        "--http-path",
        help="URL path for HTTP/SSE transports (default: /mcp).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args(argv)


def build_cli_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    if args.alias_files:
        overrides["alias_files"] = [str(Path(p).expanduser()) for p in args.alias_files]
    if args.allow_patterns:
        overrides["allow_patterns"] = list(args.allow_patterns)
    if args.default_cwd:
        overrides["default_cwd"] = str(Path(args.default_cwd).expanduser())
    if args.hot_reload is not None:
        overrides["enable_hot_reload"] = bool(args.hot_reload)

    execution: Dict[str, Any] = {}
    if args.max_stdout_bytes is not None:
        execution["max_stdout_bytes"] = args.max_stdout_bytes
    if args.max_stderr_bytes is not None:
        execution["max_stderr_bytes"] = args.max_stderr_bytes
    if args.default_timeout_seconds is not None:
        execution["default_timeout_seconds"] = args.default_timeout_seconds
    if execution:
        overrides["execution"] = execution

    if args.allow_cwd_roots:
        overrides["allow_cwd_roots"] = [str(Path(p).expanduser()) for p in args.allow_cwd_roots]
    if args.transport:
        overrides["transport"] = args.transport
    if args.http_host:
        overrides["http_host"] = args.http_host
    if args.http_port is not None:
        overrides["http_port"] = args.http_port
    if args.http_path:
        overrides["http_path"] = args.http_path

    return overrides


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    overrides = build_cli_overrides(args)
    config = Config.load(config_path=args.config, cli_overrides=overrides)
    logger.info("Starting MCP Shell Aliases server")
    run(config)


if __name__ == "__main__":
    main()
