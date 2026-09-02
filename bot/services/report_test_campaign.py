from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.config import AppSettings, get_settings
from bot.core.emojis import valid_custom_emoji_id
from bot.database.models import ActivityLog, Product
from bot.services.logs import ActivityLogService
from bot.services.order_reports import (
    OrderReportPayload,
    OrderReportService,
    resolve_report_product_emoji_id,
)

logger = logging.getLogger(__name__)

SYNTHETIC_REPORT_ACTION = "order.synthetic_channel_report_sent"
SYNTHETIC_REPORT_ENTITY = "synthetic_report"


@dataclass(frozen=True, slots=True)
class CampaignSlot:
    day_index: int
    slot_index: int
    global_index: int
    scheduled_at: datetime

    @property
    def key(self) -> str:
        return f"{self.day_index:02d}:{self.slot_index:02d}"


def parse_campaign_start(value: str) -> datetime:
    text = value.strip()
    if not text:
        raise ValueError("REPORT_TEST_CAMPAIGN_START is empty")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_campaign_slots(
    start_at: datetime,
    *,
    days: int,
    daily_count: int,
    seed: str,
) -> list[CampaignSlot]:
    """Build a stable pseudo-random schedule spread across each 24-hour campaign day."""

    total_days = max(1, min(int(days), 31))
    count = max(1, min(int(daily_count), 96))
    start = start_at.astimezone(UTC)
    seconds_per_day = 24 * 60 * 60
    bucket = seconds_per_day / count
    slots: list[CampaignSlot] = []

    for day_index in range(total_days):
        rng = random.Random(f"{seed}:{day_index}")
        day_start = start + timedelta(days=day_index)
        for slot_index in range(count):
            global_index = day_index * count + slot_index
            if day_index == 0 and slot_index == 0:
                offset_seconds = 0
            else:
                low = int(slot_index * bucket)
                high = max(low, int((slot_index + 1) * bucket) - 1)
                offset_seconds = rng.randint(low, high)
            slots.append(
                CampaignSlot(
                    day_index=day_index,
                    slot_index=slot_index,
                    global_index=global_index,
                    scheduled_at=day_start + timedelta(seconds=offset_seconds),
                )
            )
    return slots


def synthetic_buyer_id(seed: str, global_index: int) -> str:
    """Return a visibly synthetic but unique masked identifier for test reports."""

    digest = hashlib.sha256(f"{seed}:{global_index}".encode()).digest()
    prefix = 10 + digest[0] % 90
    suffix = 1000 + global_index
    return f"TEST-{prefix}****{suffix:04d}"


def pick_product(products: list[Product], *, global_index: int, seed: str) -> Product:
    """Randomize product order while covering every eligible product before repeating."""

    if not products:
        raise LookupError("No eligible products are available for the report test campaign")
    cycle, position = divmod(global_index, len(products))
    indexes = list(range(len(products)))
    random.Random(f"{seed}:products:{cycle}").shuffle(indexes)
    return products[indexes[position]]


async def _eligible_products(session: AsyncSession, min_price: int) -> list[Product]:
    return list(
        (
            await session.scalars(
                select(Product)
                .where(
                    Product.is_active.is_(True),
                    Product.price > max(0, int(min_price)),
                )
                .order_by(Product.id)
            )
        ).all()
    )


async def _sent_slot_keys(session: AsyncSession, campaign_id: str) -> set[str]:
    prefix = f"{campaign_id}:"
    values = list(
        (
            await session.scalars(
                select(ActivityLog.entity_id).where(
                    ActivityLog.action == SYNTHETIC_REPORT_ACTION,
                    ActivityLog.entity_type == SYNTHETIC_REPORT_ENTITY,
                    ActivityLog.entity_id.like(f"{prefix}%"),
                )
            )
        ).all()
    )
    return {
        value.removeprefix(prefix)
        for value in values
        if isinstance(value, str) and value.startswith(prefix)
    }


async def _send_slot(
    session: AsyncSession,
    bot: Bot,
    settings: AppSettings,
    *,
    slot: CampaignSlot,
    campaign_id: str,
    products: list[Product],
) -> None:
    product = pick_product(
        products,
        global_index=slot.global_index,
        seed=settings.report_test_campaign_seed,
    )
    service = OrderReportService(session, bot, settings)
    report_emojis = await service._report_emoji_ids()
    contextual_emoji_id = await service._contextual_emoji_id(product.category_id)
    product_emoji_id = resolve_report_product_emoji_id(
        configured=report_emojis.get("product"),
        product=product.custom_emoji_id,
        contextual=contextual_emoji_id,
    )
    button_emoji_id = (
        report_emojis.get("button")
        or valid_custom_emoji_id(settings.order_report_button_emoji_id)
        or contextual_emoji_id
        or product_emoji_id
    )

    buyer = synthetic_buyer_id(settings.report_test_campaign_seed, slot.global_index)
    delivery = await service._deliver(
        OrderReportPayload(
            buyer=buyer,
            product_name=f"[تست سیستم] {product.name}",
            quantity=1,
            amount=int(product.price),
            created_at=datetime.now(UTC),
            product_emoji=product.emoji or "💎",
            is_test=True,
        ),
        shop_name=settings.shop_name,
        product_custom_emoji_id=product_emoji_id,
        text_custom_emoji_ids=report_emojis,
        button_custom_emoji_id=button_emoji_id,
        verify_permissions=False,
    )

    await ActivityLogService(session).record(
        SYNTHETIC_REPORT_ACTION,
        entity_type=SYNTHETIC_REPORT_ENTITY,
        entity_id=f"{campaign_id}:{slot.key}",
        details={
            "campaign_id": campaign_id,
            "scheduled_at": slot.scheduled_at.isoformat(),
            "sent_at": datetime.now(UTC).isoformat(),
            "product_id": product.id,
            "product_name": product.name,
            "amount": int(product.price),
            "buyer": buyer,
            "chat_id": delivery.chat_id,
            "message_id": delivery.message_id,
            "premium_emoji_used": delivery.premium_emoji_used,
            "synthetic": True,
        },
    )
    logger.info(
        "Synthetic report test sent campaign=%s slot=%s product_id=%s amount=%s message_id=%s",
        campaign_id,
        slot.key,
        product.id,
        product.price,
        delivery.message_id,
    )


async def run_report_test_campaign_worker(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    settings: AppSettings | None = None,
) -> None:
    """Send clearly labeled synthetic channel reports without creating real orders."""

    config = settings or get_settings()
    if not config.report_test_campaign_enabled:
        return
    if config.order_report_target is None:
        logger.warning("Report test campaign disabled: ORDER_REPORT_CHANNEL_ID is not configured")
        return

    try:
        start_at = parse_campaign_start(config.report_test_campaign_start)
    except ValueError:
        logger.exception("Report test campaign has an invalid start time")
        return

    days = max(1, min(int(config.report_test_campaign_days), 31))
    daily_count = max(1, min(int(config.report_test_campaign_daily_count), 96))
    slots = build_campaign_slots(
        start_at,
        days=days,
        daily_count=daily_count,
        seed=config.report_test_campaign_seed,
    )
    campaign_end = start_at + timedelta(days=days)
    campaign_id = hashlib.sha256(
        f"{start_at.isoformat()}:{days}:{daily_count}:{config.report_test_campaign_seed}".encode()
    ).hexdigest()[:16]
    poll_seconds = max(10, min(int(config.report_test_campaign_poll_seconds), 300))

    logger.info(
        "Synthetic report test campaign armed id=%s start=%s end=%s daily_count=%s min_price=%s",
        campaign_id,
        start_at.isoformat(),
        campaign_end.isoformat(),
        daily_count,
        config.report_test_campaign_min_price,
    )

    while True:
        now = datetime.now(UTC)
        try:
            async with session_factory() as session:
                sent_keys = await _sent_slot_keys(session, campaign_id)
                due = [
                    slot
                    for slot in slots
                    if slot.scheduled_at <= now and slot.key not in sent_keys
                ]
                if due:
                    products = await _eligible_products(
                        session, config.report_test_campaign_min_price
                    )
                    if not products:
                        logger.error(
                            "Synthetic report test campaign has no active products above %s تومان",
                            config.report_test_campaign_min_price,
                        )
                    else:
                        # Limit catch-up bursts after a restart while still recovering missed slots.
                        for slot in due[:2]:
                            await _send_slot(
                                session,
                                bot,
                                config,
                                slot=slot,
                                campaign_id=campaign_id,
                                products=products,
                            )
                            await asyncio.sleep(2)

                if now >= campaign_end:
                    sent_keys = await _sent_slot_keys(session, campaign_id)
                    if len(sent_keys) >= len(slots):
                        logger.info(
                            "Synthetic report test campaign completed id=%s total=%s",
                            campaign_id,
                            len(slots),
                        )
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Synthetic report test campaign iteration failed")

        await asyncio.sleep(poll_seconds)
