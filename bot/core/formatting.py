from __future__ import annotations

from datetime import datetime
from html import escape

from bot.core.emojis import valid_custom_emoji_id
from bot.database.enums import OrderStatus, TicketStatus

ORDER_STATUS_FA = {
    OrderStatus.PENDING: "🕐 در انتظار بررسی",
    OrderStatus.APPROVED: "✅ تأیید شده",
    OrderStatus.PROCESSING: "⚙️ در حال انجام",
    OrderStatus.COMPLETED: "🎉 تکمیل شده",
    OrderStatus.CANCELLED: "❌ لغو شده",
}

TICKET_STATUS_FA = {
    TicketStatus.OPEN: "🟢 باز",
    TicketStatus.ANSWERED: "🔵 پاسخ داده شده",
    TicketStatus.CLOSED: "⚫ بسته",
}


def money(amount: int, currency: str = "تومان") -> str:
    return f"{amount:,} {currency}"


def dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y/%m/%d • %H:%M")


def h(value: object) -> str:
    return escape(str(value), quote=True)


def custom_emoji(emoji_id: str | None, fallback: str) -> str:
    emoji_id = valid_custom_emoji_id(emoji_id)
    if emoji_id is None:
        return fallback
    return f'<tg-emoji emoji-id="{h(emoji_id)}">{fallback}</tg-emoji>'


def compact_text(value: str, max_length: int = 32) -> str:
    clean = " ".join(value.split())
    return clean if len(clean) <= max_length else f"{clean[: max_length - 1]}…"
