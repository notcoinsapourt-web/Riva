from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base


class WebUser(Base):
    __tablename__ = "web_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebWallet(Base):
    __tablename__ = "web_wallets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebWalletTransaction(Base):
    __tablename__ = "web_wallet_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    wallet_id: Mapped[int] = mapped_column(BigInteger, index=True)
    transaction_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(BigInteger)
    balance_before: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text)
    reference_type: Mapped[str | None] = mapped_column(String(40))
    reference_id: Mapped[str | None] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebCheckoutBatch(Base):
    __tablename__ = "web_checkout_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    batch_number: Mapped[str] = mapped_column(String(30), unique=True)
    checkout_key: Mapped[str] = mapped_column(String(120), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    total_amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebOrder(Base):
    __tablename__ = "web_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    batch_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product_id: Mapped[int | None] = mapped_column(BigInteger)
    product_name: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[int] = mapped_column(BigInteger)
    customer_input: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    admin_note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebDeposit(Base):
    __tablename__ = "web_deposits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    method: Mapped[str] = mapped_column(String(20))
    amount: Mapped[int] = mapped_column(BigInteger)
    proof_name: Mapped[str] = mapped_column(Text)
    proof_mime: Mapped[str] = mapped_column(String(80))
    proof_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    transaction_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewed_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
