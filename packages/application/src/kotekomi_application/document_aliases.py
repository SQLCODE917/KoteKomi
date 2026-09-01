"""Deterministic source-literal alias declarations."""

from __future__ import annotations

import re

_FUNCTION_WORDS = frozenset({"a", "an", "and", "at", "for", "in", "of", "on", "the", "to"})
_PARENTHETICAL_NAME = re.compile(r"^(?P<expanded>.+?)\s+\((?P<alias>[^()]+)\)$")
_DOTTED_GEOGRAPHIC_PREFIX = re.compile(r"^(?:[A-Z]\.){2,}\s+")
_UPPER_GEOGRAPHIC_PREFIX = re.compile(r"^[A-Z]{2,3}\s+")
_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+")


def parse_parenthetical_alias(text: str) -> tuple[str, str, bool] | None:
    """Parse one literal expanded-name and initialism declaration."""
    matched = _PARENTHETICAL_NAME.fullmatch(text)
    if matched is None:
        return None
    expanded = matched.group("expanded")
    alias = matched.group("alias")
    normalized_alias = initialism_value(alias)
    if len(normalized_alias) < 2 or normalized_alias != alias.upper().replace(".", ""):
        return expanded, alias, False
    candidates = (initialism(expanded), initialism(remove_geographic_prefix(expanded)))
    return expanded, alias, normalized_alias in candidates


def initialism(text: str) -> str:
    """Return the established KoteKomi initialism for one literal name."""
    values: list[str] = []
    for word in _WORD.findall(text):
        if word.casefold() in _FUNCTION_WORDS:
            continue
        values.append(word if word.isupper() and len(word) > 1 else word[0])
    return initialism_value("".join(values))


def initialism_value(text: str) -> str:
    """Normalize an initialism without changing source identity."""
    return "".join(character for character in text.upper() if character.isalnum())


def remove_geographic_prefix(text: str) -> str:
    """Remove the established dotted or uppercase geographic name prefix."""
    dotted = _DOTTED_GEOGRAPHIC_PREFIX.sub("", text, count=1)
    if dotted != text:
        return dotted
    return _UPPER_GEOGRAPHIC_PREFIX.sub("", text, count=1)
