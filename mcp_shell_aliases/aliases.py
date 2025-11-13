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

"""Alias parsing and catalog management."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import shlex
import shutil
from pathlib import Path
from typing import Dict, List

from .safety import SafetyClassifier

logger = logging.getLogger(__name__)

ALIAS_REGEX = re.compile(
    r"^alias\s+(?P<name>[A-Za-z0-9_\-]+)=(?P<quote>['\"])(?P<expansion>.*)(?P=quote)\s*$"
)


@dataclass(slots=True)
class Alias:
    """Represents a parsed shell alias."""

    name: str
    expansion: str
    safe: bool
    source_file: Path


class AliasCatalog:
    """Catalog of aliases discovered from configured files."""

    def __init__(self, aliases: Dict[str, Alias]):
        self._aliases = dict(aliases)

    def get(self, name: str) -> Alias | None:
        return self._aliases.get(name)

    def all(self) -> List[Alias]:
        return list(self._aliases.values())


def build_catalog(alias_files: List[Path], classifier: SafetyClassifier) -> AliasCatalog:
    """Parse configured files and build alias catalog."""
    aliases: Dict[str, Alias] = {}

    for path in alias_files:
        parsed = _parse_file(path, classifier)
        for alias in parsed:
            existing = aliases.get(alias.name)
            if existing is None:
                aliases[alias.name] = alias
                continue

            # Prefer overrides whose head command is actually available on this system.
            # This helps when dotfiles define OS-conditional aliases like `gls` (GNU ls)
            # that are not present on Linux. Without evaluating shell conditionals, we
            # approximate intent by refusing to override with an unavailable command.
            if _can_override(existing, alias):
                logger.debug(
                    "Alias %s overridden by %s (previous source %s)",
                    alias.name,
                    alias.source_file,
                    existing.source_file,
                )
                aliases[alias.name] = alias

    return AliasCatalog(aliases)


def _parse_file(path: Path, classifier: SafetyClassifier) -> List[Alias]:
    if not path.exists():
        logger.warning("Alias file %s does not exist", path)
        return []

    aliases: List[Alias] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        match = ALIAS_REGEX.match(stripped)
        if not match:
            continue

        name = match.group("name")
        expansion = _unescape(match.group("expansion"), match.group("quote"))

        if _is_invalid_name(name):
            logger.debug("Skipping alias %s with invalid name in %s:%d", name, path, idx)
            continue

        safe = classifier.is_safe(expansion)
        aliases.append(Alias(name=name, expansion=expansion, safe=safe, source_file=path))

    return aliases


def _unescape(expansion: str, quote: str) -> str:
    if quote == "'":
        return expansion.replace("\\'", "'")
    if quote == '"':
        return expansion.replace('\\"', '"')
    return expansion


def _is_invalid_name(name: str) -> bool:
    return bool(re.search(r"[\s!$`\\-]", name))


_BUILTIN_OK: set[str] = {
    # Common bash builtins that are valid in non-interactive shells
    "echo",
    "printf",
    "source",
    "." ,
    "test",
    "true",
    "false",
}


def _head_command(expansion: str) -> str | None:
    try:
        parts = shlex.split(expansion, posix=True)
    except ValueError:
        return None
    return parts[0] if parts else None


def _is_command_available(cmd: str | None) -> bool:
    if not cmd:
        return False
    if cmd in _BUILTIN_OK:
        return True
    return shutil.which(cmd) is not None


def _can_override(existing: Alias, candidate: Alias) -> bool:
    """Decide whether a duplicate alias should override the existing one.

    Heuristic: allow override if the candidate's head command is available.
    If not available but the existing one's command is also unavailable, allow
    override (last-wins). Otherwise, keep the existing definition.
    """
    cand_cmd = _head_command(candidate.expansion)
    exist_cmd = _head_command(existing.expansion)

    cand_ok = _is_command_available(cand_cmd)
    if cand_ok:
        return True

    exist_ok = _is_command_available(exist_cmd)
    return not exist_ok
