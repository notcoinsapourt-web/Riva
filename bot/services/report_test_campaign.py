from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
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
from bot.services.settings import SettingsService

logger = logging.getLogger(__name__)

SYNTHETIC_REPORT_ACTION = "order.synthetic_channel_report_sent"
SYNTHETIC_REPORT_ENTITY = "synthetic_report"
CAMPAIGN_CHANNEL_SETTING = "report_test_campaign_channel_id"
CAMPAIGN_CHANNEL_TITLE_SETTING = "report_test_campaign_channel_title"
CAMPAIGN_STARTED_AT_SETTING = "report_test_campaign_started_at"
MASKED_BUYER_RE = re.compile(r"^\d{2}\*{6}\d{2}$")


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
    """Return a deterministic, unique masked pseudo-ID for the private test channel."""

    # 37 is coprime to 10,000, so the visible prefix+suffix pair cannot repeat
    # during this 280-message campaign. The seed changes the starting offset.
    offset = int.from_bytes(hashlib.sha256(seed.encode()).digest()[:2], "big") % 10_000
    value = (offset + max(0, int(global_index)) * 37) % 10_000
    prefix, suffix = divmod(value, 100)
    return f"{prefix:02d}******{suffix:02d}"


def pick_product(products: list[Product], *, global_index: int, seed: str) -> Product:
    """Randomize product order while covering every eligible product before repeating."""

    if not products:
        raise LookupError("No eligible products are available for the report test campaign")
    cycle, position = divmod(global_index, len(products))
    indexes = list(range(len(products)))
    random.Random(f"{seed}:products:{cycle}").shuffle(indexes)
    return products[indexes[position]]


async def bind_private_test_channel(
    session: AsyncSession,
    bot: Bot,
    settings: AppSettings,
    chat_id: int,
    *,
    actor_user_id: int | None = None,
    force: bool = False,
) -> bool:
    """Bind the campaign to a private channel where this bot can post.

    The production report target is explicitly rejected. No orders or user data
    are created by this binding.
    """

    if not settings.report_test_campaign_enabled:
        return False
    if actor_user_id is not None and settings.admin_ids and actor_user_id not in settings.admin_ids:
        logger.warning("Ignored private test-channel bind from non-admin user_id=%s", actor_user_id)
        return False

    chat = await bot.get_chat(chat_id)
    chat_type = getattr(chat.type, "value", str(chat.type))
    if chat_type != "channel" or getattr(chat, "username", None):
        logger.warning("Ignored report test bind: chat_id=%s is not a private channel", chat_id)
        return False

    production_target = settings.order_report_target
    if production_target is not None and str(production_target) == str(chat.id):
        logger.error("Refusing to bind report test campaign to the production report channel")
        return False

    me = await bot.get_me()
    member = await bot.get_chat_member(chat.id, me.id)
    status = getattr(member.status, "value", str(member.status))
    if status not in {"administrator", "creator"}:
        logger.warning("Cannot bind private test channel: bot status=%s", status)
        return False
    if status == "administrator" and getattr(member, "can_post_messages", True) is False:
        logger.warning("Cannot bind private test channel: bot lacks can_post_messages")
        return False

    service = SettingsService(session)
    existing = (await service.get(CAMPAIGN_CHANNEL_SETTING, "")).strip()
    if existing and existing != str(chat.id) and not force:
        logger.warning(
            "Private test channel already bound to %s; ignored candidate %s",
            existing,
            chat.id,
        )
        return False

    await service.set(
        CAMPAIGN_CHANNEL_SETTING,
        chat.id,
        description="Private channel used only by the temporary report delivery campaign.",
    )
    await service.set(
        CAMPAIGN_CHANNEL_TITLE_SETTING,
        getattr(chat, "title", "") or "",
        description="Human-readable title of the private report test channel.",
    )
    if not await service.get(CAMPAIGN_STARTED_AT_SETTING, "") or force:
        await service.set(
            CAMPAIGN_STARTED_AT_SETTING,
            _preferred_start_time(settings).isoformat(),
            description="Actual start of the temporary private report test campaign.",
        )

    logger.info(
        "Private report test channel bound chat_id=%s title=%r force=%s",
        chat.id,
        getattr(chat, "title", ""),
        force,
    )
    return True


def _preferred_start_time(settings: AppSettings) -> datetime:
    """Use the requested start when fresh; otherwise start when the channel is bound."""

    now = datetime.now(UTC)
    if settings.report_test_campaign_start.strip():
        try:
            configured = parse_campaign_start(settings.report_test_campaign_start)
        except ValueError:
            configured = now
        # Avoid a large catch-up burst if the private channel was connected much later.
        if now - timedelta(minutes=15) <= configured <= now + timedelta(minutes=2):
            return configured
    return now


async def _campaign_target(session: AsyncSession, settings: AppSettings) -> int | str | None:
    env_target = settings.report_test_campaign_target
    if env_target is not None:
        return env_target
    stored = (await SettingsService(session).get(CAMPAIGN_CHANNEL_SETTING, "")).strip()
    if not stored:
        return None
    if stored.lstrip("-").isdigit():
        return int(stored)
    return AppSettings._chat_target(stored)


async def _campaign_start(session: AsyncSession, settings: AppSettings) -> datetime:
    service = SettingsService(session)
    stored = (await service.get(CAMPAIGN_STARTED_AT_SETTING, "")).strip()
    if stored:
        try:
            return parse_campaign_start(stored)
        except ValueError:
            logger.warning("Stored report test campaign start is invalid; replacing it")
    start = _preferred_start_time(settings)
    await service.set(
        CAMPAIGN_STARTED_AT_SETTING,
        start.isoformat(),
        description="Actual start of the temporary private report test campaign.",
    )
    return start


async def _validate_private_target(bot: Bot, settings: AppSettings, target: int | str) -> int:
    chat = await bot.get_chat(target)
    chat_type = getattr(chat.type, "value", str(chat.type))
    if chat_type != "channel" or getattr(chat, "username", None):
        raise RuntimeError("Report test campaign target must be a private Telegram channel")
    if settings.order_report_target is not None and str(settings.order_report_target) == str(chat.id):
        raise RuntimeError("Report test campaign target must differ from production reports channel")
    me = await bot.get_me()
    member = await bot.get_chat_member(chat.id, me.id)
    status = getattr(member.status, "value", str(member.status))
    if status not in {"administrator", "creator"}:
        raise RuntimeError(f"Bot must be an administrator in private test channel; status={status}")
    if status == "administrator" and getattr(member, "can_post_messages", True) is False:
        raise RuntimeError("Bot lacks can_post_messages in private test channel")
    return int(chat.id)


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
    target: int,
    slot: CampaignSlot,
    campaign_id: str,
    products: list[Product],
) -> None:
    product = pick_product(
        products,
        global_index=slot.global_index,
        seed=settings.report_test_campaign_seed,
    )
    delivery_settings = settings.model_copy(update={"order_report_channel_id": str(target)})
    service = OrderReportService(session, bot, delivery_settings)
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
    shop_name = await SettingsService(session).get("shop_name", settings.shop_name)
    delivery = await service._deliver(
        OrderReportPayload(
            buyer=buyer,
            product_name=product.name,
            quantity=1,
            amount=int(product.price),
            created_at=datetime.now(UTC),
            product_emoji=product.emoji or "💎",
            # This is a private, isolated test channel. Keep the visible card
            # identical to the production format while retaining synthetic=true
            # only in the internal activity log below.
            is_test=False,
        ),
        shop_name=shop_name,
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
            "creates_order": False,
        },
    )
    logger.info(
        "Private report delivery test sent campaign=%s slot=%s product_id=%s amount=%s message_id=%s",
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
    """Send 20 isolated report-format messages per day for a bounded private test campaign."""

    config = settings or get_settings()
    if not config.report_test_campaign_enabled:
        return

    days = max(1, min(int(config.report_test_campaign_days), 31))
    daily_count = max(1, min(int(config.report_test_campaign_daily_count), 96))
    poll_seconds = max(10, min(int(config.report_test_campaign_poll_seconds), 300))

    active_target: int | None = None
    start_at: datetime | None = None
    campaign_end: datetime | None = None
    campaign_id = ""
    slots: list[CampaignSlot] = []
    waiting_logged = False

    while True:
        now = datetime.now(UTC)
        try:
            async with session_factory() as session:
                raw_target = await _campaign_target(session, config)
                if raw_target is None:
                    if not waiting_logged:
                        logger.info(
                            "Private report test campaign is waiting for a bound private channel"
                        )
                        waiting_logged = True
                    await asyncio.sleep(poll_seconds)
                    continue

                target = await _validate_private_target(bot, config, raw_target)
                waiting_logged = False
                if active_target != target or start_at is None:
                    active_target = target
                    start_at = await _campaign_start(session, config)
                    campaign_end = start_at + timedelta(days=days)
                    slots = build_campaign_slots(
                        start_at,
                        days=days,
                        daily_count=daily_count,
                        seed=config.report_test_campaign_seed,
                    )
                    campaign_id = hashlib.sha256(
                        (
                            f"{target}:{start_at.isoformat()}:{days}:{daily_count}:"
                            f"{config.report_test_campaign_seed}"
                        ).encode()
                    ).hexdigest()[:16]
                    logger.info(
                        "Private report test campaign armed id=%s target=%s start=%s end=%s "
                        "daily_count=%s min_price=%s",
                        campaign_id,
                        target,
                        start_at.isoformat(),
                        campaign_end.isoformat(),
                        daily_count,
                        config.report_test_campaign_min_price,
                    )

                assert campaign_end is not None
                sent_keys = await _sent_slot_keys(session, campaign_id)
                if now >= campaign_end:
                    if len(sent_keys) == len(slots):
                        logger.info(
                            "Private report test campaign completed id=%s total=%s",
                            campaign_id,
                            len(sent_keys),
                        )
                    else:
                        logger.error(
                            "Private report test campaign ended id=%s sent=%s expected=%s; "
                            "no messages will be sent after the 14-day window",
                            campaign_id,
                            len(sent_keys),
                            len(slots),
                        )
                    return

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
                            "Private report test campaign has no active products above %s تومان",
                            config.report_test_campaign_min_price,
                        )
                    else:
                        # Recover short deployment gaps without creating a large instant burst.
                        for slot in due[:2]:
                            await _send_slot(
                                session,
                                bot,
                                config,
                                target=active_target,
                                slot=slot,
                                campaign_id=campaign_id,
                                products=products,
                            )
                            await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Private report test campaign iteration failed")

        await asyncio.sleep(poll_seconds)
