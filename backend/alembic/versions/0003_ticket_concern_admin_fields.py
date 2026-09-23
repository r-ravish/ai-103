"""
Ticket admin fields and concern tracking.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-21

Changes:
    * tickets.is_acknowledged    -- boolean default false indicating whether concern is taken into account
    * tickets.acknowledged_at    -- timestamp when concern was taken into account
    * tickets.acknowledged_by_id -- foreign key to users.id for admin who acknowledged it
    * tickets.admin_notes        -- text column for admin review notes or resolution explanation
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("is_acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "tickets",
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column(
            "acknowledged_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "tickets",
        sa.Column("admin_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_tickets_is_acknowledged", "tickets", ["is_acknowledged"])


def downgrade() -> None:
    op.drop_index("ix_tickets_is_acknowledged", table_name="tickets")
    op.drop_column("tickets", "admin_notes")
    op.drop_column("tickets", "acknowledged_by_id")
    op.drop_column("tickets", "acknowledged_at")
    op.drop_column("tickets", "is_acknowledged")
