"""FastMCP server exposing shell aliases as tools and resources."""

from __future__ import annotations

import json
import logging
import signal
from dataclasses import dataclass
from pathlib import Path
from types import FrameType
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import __version__
from .aliases import Alias, AliasCatalog, build_catalog
from .config import Config
from .errors import AliasNotFoundError, CwdNotAllowedError
from .execution import execute_alias, write_audit_log
from .safety import SafetyClassifier

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AliasRuntime:
    """Runtime helpers shared by tools and resources."""

    config: Config
    classifier: SafetyClassifier
    catalog: AliasCatalog

    @classmethod
    def build(cls, config: Config) -> "AliasRuntime":
        classifier = SafetyClassifier.from_strings(config.allow_patterns, config.deny_patterns)
        catalog = build_catalog(config.alias_files, classifier)
        return cls(config=config, classifier=classifier, catalog=catalog)

    def refresh(self) -> None:
        if not self.config.enable_hot_reload:
            return
        logger.debug("Reloading alias catalog due to hot reload")
        self.catalog = build_catalog(self.config.alias_files, self.classifier)

    def get_alias(self, name: str) -> Alias:
        self.refresh()
        alias = self.catalog.get(name)
        if alias is None:
            raise AliasNotFoundError(f"Alias '{name}' is not defined")
        return alias

    def list_aliases(self) -> List[Alias]:
        self.refresh()
        return self.catalog.all()


def create_app(config: Config) -> FastMCP:
    runtime = AliasRuntime.build(config)
    server = FastMCP(
        "bash-aliases",
        instructions="Expose vetted shell aliases as safe MCP tools.",
        version=__version__,
    )

    def example_for_alias(alias: Alias) -> str:
        base = f'alias.exec {{"name":"{alias.name}","args":"","dryRun": true}}'
        if alias.safe:
            return base
        return f'{base}  # unsafe aliases only support dry runs'

    def alias_to_payload(alias: Alias) -> Dict[str, Any]:
        return {
            "name": alias.name,
            "expansion": alias.expansion,
            "safe": alias.safe,
            "sourceFile": str(alias.source_file),
            "example": example_for_alias(alias),
        }

    @server.tool(name="alias.exec", description="Execute or dry-run a configured shell alias.")
    async def alias_exec(
        name: str,
        args: Optional[str] = None,
        dry_run: bool = True,
        confirm: bool = False,
        cwd: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not dry_run and not confirm:
            raise ToolError("Execution requires confirm=true; dry_run is enabled otherwise.")

        try:
            alias = runtime.get_alias(name)
        except AliasNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        if not alias.safe and not dry_run:
            raise ToolError(
                "Alias is not marked safe. Only dry_run executions are permitted unless it matches allow patterns."
            )

        requested_cwd = Path(cwd) if cwd else None
        normalized_args = args.strip() if args and args.strip() else None

        timeout_override = None
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ToolError("timeout_seconds must be positive.")
            max_timeout = max(runtime.config.execution.default_timeout_seconds, 1) * 5
            if timeout_seconds > max_timeout:
                raise ToolError(f"timeout_seconds may not exceed {max_timeout} seconds.")
            timeout_override = timeout_seconds

        try:
            result = await execute_alias(
                alias,
                args=normalized_args,
                config=runtime.config,
                dry_run=dry_run,
                requested_cwd=requested_cwd,
                timeout_override=timeout_override,
            )
        except CwdNotAllowedError as exc:
            raise ToolError(str(exc)) from exc

        write_audit_log(
            config=runtime.config,
            alias=alias,
            args=normalized_args,
            cwd=result.cwd,
            result=result,
        )

        payload = result.to_payload()
        payload["aliasSafe"] = alias.safe
        payload["sourceFile"] = str(alias.source_file)
        return payload

    @server.tool(name="alias.catalog", description="Return catalog metadata for all aliases.")
    async def alias_catalog_tool() -> Dict[str, List[Dict[str, Any]]]:
        aliases = runtime.list_aliases()
        return {
            "aliases": [alias_to_payload(alias) for alias in aliases],
        }

    @server.resource("alias://catalog", description="JSON catalog of available aliases.", mime_type="application/json")
    async def alias_catalog_resource() -> str:
        aliases = runtime.list_aliases()
        body = json.dumps([alias_to_payload(alias) for alias in aliases], indent=2)
        return body

    @server.resource("alias://{alias_name}", mime_type="application/json")
    async def alias_detail_resource(alias_name: str) -> str:
        try:
            alias = runtime.get_alias(alias_name)
        except AliasNotFoundError as exc:
            raise ToolError(str(exc)) from exc

        body = json.dumps(alias_to_payload(alias), indent=2)
        return body

    return server


def run(config: Config) -> None:
    server = create_app(config)
    # Install basic signal handlers so we can log clean shutdown intent.
    def _handle_signal(signum: int, _frame: FrameType | None) -> None:  # pragma: no cover - dependent on signal delivery
        logger.info("Received signal %s; shutting down.", signum)
        raise KeyboardInterrupt

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, AttributeError):  # pragma: no cover - platform limitations
            pass

    try:
        if hasattr(server, "run_stdio"):
            server.run_stdio()
        elif hasattr(server, "run"):
            server.run()
        else:  # pragma: no cover - safety guard for unexpected fastmcp versions
            raise RuntimeError("FastMCP server implementation missing run method")
    except KeyboardInterrupt:
        logger.info("Server stopped by user request.")
