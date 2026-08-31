"""Product module facade; customer handlers live in :mod:`bot.modules.catalog`."""

from bot.modules.catalog.router import router

__all__ = ["router"]
