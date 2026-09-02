from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from bot.config import AppSettings
from bot.services.report_test_campaign import (
    build_campaign_slots,
    parse_campaign_start,
    synthetic_buyer_id,
)


def test_campaign_has_twenty_spread_slots_per_day_and_starts_immediately() -> None:
    start = datetime(2026, 9, 2, 12, 5, 42, tzinfo=UTC)
    slots = build_campaign_slots(start, days=14, daily_count=20, seed="campaign")

    assert len(slots) == 280
    assert slots[0].scheduled_at == start

    for day_index in range(14):
        daily = [slot for slot in slots if slot.day_index == day_index]
        assert len(daily) == 20
        day_start = start + timedelta(days=day_index)
        day_end = day_start + timedelta(days=1)
        assert all(day_start <= slot.scheduled_at < day_end for slot in daily)
        assert daily == sorted(daily, key=lambda item: item.scheduled_at)


def test_schedule_is_deterministic_for_restart_safety() -> None:
    start = datetime(2026, 9, 2, tzinfo=UTC)
    first = build_campaign_slots(start, days=2, daily_count=20, seed="same")
    second = build_campaign_slots(start, days=2, daily_count=20, seed="same")

    assert first == second


def test_synthetic_buyer_ids_match_normal_masked_format_and_are_unique() -> None:
    buyers = [synthetic_buyer_id("campaign", index) for index in range(280)]

    assert len(set(buyers)) == 280
    assert all(re.fullmatch(r"\d{2}\*{6}\d{2}", value) for value in buyers)
    assert all("TEST" not in value for value in buyers)


def test_campaign_start_accepts_utc_z_suffix() -> None:
    parsed = parse_campaign_start("2026-09-02T12:05:42Z")
    assert parsed == datetime(2026, 9, 2, 12, 5, 42, tzinfo=UTC)


def test_private_invite_link_is_never_misread_as_bot_api_target() -> None:
    assert AppSettings._chat_target("https://t.me/+zEc9S4ARna0zYWY5") is None
    assert AppSettings._chat_target("-1004360571325") == -1004360571325
