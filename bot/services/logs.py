from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ActivityLog


class ActivityLogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        action: str,
        *,
        actor_user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: object | None = None,
        details: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> ActivityLog:
        item = ActivityLog(
            actor_user_id=actor_user_id,
            action=action[:100],
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            details=details or {},
        )
        self.session.add(item)
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        return item
