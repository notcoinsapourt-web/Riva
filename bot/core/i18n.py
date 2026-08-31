from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any


class I18n:
    """Small dependency-free translation layer with Persian fallback."""

    def __init__(self, default_language: str = "fa") -> None:
        self.default_language = default_language

    def text(self, key: str, language: str | None = None, **values: Any) -> str:
        language = (language or self.default_language).split("-")[0].lower()
        catalog = _catalog(language)
        fallback = _catalog("fa")
        template = catalog.get(key, fallback.get(key, key))
        return template.format_map(_SafeValues(values))


class _SafeValues(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@lru_cache(maxsize=8)
def _catalog(language: str) -> dict[str, str]:
    path = files("bot.locales").joinpath(f"{language}.json")
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
