from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.core.exceptions import NotFoundError, ValidationError
from bot.database.enums import TicketSender, TicketStatus
from bot.database.models import Ticket, TicketMessage


class TicketService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, user_id: int, subject: str, text: str) -> Ticket:
        if not subject.strip() or not text.strip():
            raise ValidationError("موضوع و متن تیکت الزامی است.")
        ticket = Ticket(
            number=_ticket_number(),
            user_id=user_id,
            subject=subject.strip()[:180],
            status=TicketStatus.OPEN,
        )
        self.session.add(ticket)
        await self.session.flush()
        self.session.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_type=TicketSender.USER,
                sender_user_id=user_id,
                text=text.strip()[:4000],
            )
        )
        await self.session.commit()
        return ticket

    async def get(self, ticket_id: int) -> Ticket:
        ticket = await self.session.scalar(
            select(Ticket).options(selectinload(Ticket.messages)).where(Ticket.id == ticket_id)
        )
        if ticket is None:
            raise NotFoundError("تیکت پیدا نشد.")
        return ticket

    async def user_tickets(self, user_id: int, limit: int = 20) -> list[Ticket]:
        return list(
            (
                await self.session.scalars(
                    select(Ticket)
                    .where(Ticket.user_id == user_id)
                    .order_by(Ticket.updated_at.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def open_tickets(self, limit: int = 30) -> list[Ticket]:
        return list(
            (
                await self.session.scalars(
                    select(Ticket)
                    .where(Ticket.status != TicketStatus.CLOSED)
                    .order_by(Ticket.updated_at.desc())
                    .limit(limit)
                )
            ).all()
        )

    async def reply(self, *, ticket_id: int, admin_user_id: int, text: str) -> Ticket:
        ticket = await self.get(ticket_id)
        if ticket.status == TicketStatus.CLOSED:
            raise ValidationError("این تیکت بسته شده است.")
        self.session.add(
            TicketMessage(
                ticket_id=ticket.id,
                sender_type=TicketSender.ADMIN,
                sender_user_id=admin_user_id,
                text=text.strip()[:4000],
            )
        )
        ticket.status = TicketStatus.ANSWERED
        await self.session.commit()
        return ticket

    async def close(self, ticket_id: int) -> Ticket:
        ticket = await self.get(ticket_id)
        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.now(UTC)
        await self.session.commit()
        return ticket


def _ticket_number() -> str:
    return f"TK-{datetime.now(UTC):%y%m%d}-{secrets.token_hex(2).upper()}"
