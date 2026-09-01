"""manual deposits and required channels

Revision ID: 8d91c8fd213a
Revises: 2cfa54fda9e7
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "8d91c8fd213a"
down_revision: str | Sequence[str] | None = "2cfa54fda9e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "required_channels",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("invite_link", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_required_channels_chat_id", "required_channels", ["chat_id"], unique=True)
    op.create_index(
        "ix_required_channels_is_active", "required_channels", ["is_active"], unique=False
    )
    op.create_index(
        "ix_required_channels_sort_order", "required_channels", ["sort_order"], unique=False
    )
    op.create_table(
        "manual_deposits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("number", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "method",
            sa.Enum("card", "crypto", name="deposit_method", native_enum=False),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("proof_file_id", sa.String(length=256), nullable=False),
        sa.Column("proof_file_type", sa.String(length=16), nullable=False),
        sa.Column("transaction_hash", sa.String(length=256), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="deposit_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("amount > 0", name="ck_manual_deposit_amount_positive"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manual_deposits_number", "manual_deposits", ["number"], unique=True)
    op.create_index("ix_manual_deposits_status", "manual_deposits", ["status"], unique=False)
    op.create_index("ix_manual_deposits_user_id", "manual_deposits", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("manual_deposits")
    op.drop_table("required_channels")
