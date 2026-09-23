"""
Add admin_response column to tickets for employee-visible replies.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

Changes:
    * tickets.admin_response  -- short, employee-visible text reply from admin
                                 (distinct from admin_notes which is internal only).
                                 Shown to employees when they check ticket status.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004b"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("admin_response", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tickets", "admin_response")
