"""Alias parsing and catalog management."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import re
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
            if alias.name in aliases:
                logger.debug(
                    "Alias %s overridden by %s (previous source %s)",
                    alias.name,
                    alias.source_file,
                    aliases[alias.name].source_file,
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
