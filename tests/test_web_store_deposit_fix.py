from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from bot.core.callbacks import AdminCallback
from bot.database.web_models import WebDeposit, WebWallet, WebWalletTransaction
from bot.modules.admin import web_store


class DummyCallback:
    def __init__(self, admin_id: int = 9001) -> None:
        self.from_user = SimpleNamespace(id=admin_id)
        self.answers: list[tuple[str, bool]] = []

    async def answer(
        self,
        text: str | None = None,
        *,
        show_alert: bool = False,
        **_: object,
    ) -> None:
        self.answers.append((text or "", show_alert))


@pytest.mark.asyncio
async def test_website_deposit_approval_persists_wallet_credit(
    database,
    monkeypatch,
) -> None:
    async def no_op_show_deposit(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(web_store, "show_deposit", no_op_show_deposit)
    now = datetime.now(UTC)

    async with database.session_factory() as session:
        session.add(
            WebWallet(
                id=10,
                user_id=77,
                balance=125_000,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            WebDeposit(
                id=20,
                number="WD-TEST-20",
                user_id=77,
                method="card",
                amount=250_000,
                proof_name="receipt.jpg",
                proof_mime="image/jpeg",
                proof_bytes=b"test-receipt",
                transaction_hash=None,
                status="pending",
                reviewed_by_telegram_id=None,
                reviewed_at=None,
                created_at=now,
            )
        )
        await session.commit()

    callback = DummyCallback()
    callback_data = AdminCallback(section="web", action="da", entity_id=20)
    async with database.session_factory() as session:
        await web_store.review_web_deposit(  # type: ignore[arg-type]
            callback,
            callback_data,
            session,
        )

    async with database.session_factory() as session:
        deposit = await session.get(WebDeposit, 20)
        wallet = await session.scalar(select(WebWallet).where(WebWallet.user_id == 77))
        transaction = await session.scalar(
            select(WebWalletTransaction).where(
                WebWalletTransaction.idempotency_key == "web-deposit:20"
            )
        )

        assert deposit is not None and deposit.status == "approved"
        assert deposit.reviewed_by_telegram_id == 9001
        assert wallet is not None and int(wallet.balance) == 375_000
        assert transaction is not None
        assert int(transaction.amount) == 250_000
        assert int(transaction.balance_before) == 125_000
        assert int(transaction.balance_after) == 375_000

    assert callback.answers[-1][0] == "رسید تأیید شد و موجودی کیف پول افزایش یافت."
