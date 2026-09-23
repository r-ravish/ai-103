"""
Merge migration: joins conversation-memory branch (0004) and
admin-response branch (0004b) into a single head.

Revision ID: 0005
Revises: 0004, 0004b
Create Date: 2026-09-22
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = ('0004', '0004b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Both branches have already applied their schema changes independently.
    # This migration only joins the two branch heads — no DDL needed.
    pass


def downgrade() -> None:
    pass
