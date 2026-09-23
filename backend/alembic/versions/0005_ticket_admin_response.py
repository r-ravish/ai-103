"""
Add admin_response to tickets.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22

Tables created/modified:
    tickets - added admin_response
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("tickets", sa.Column("admin_response", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("tickets", "admin_response")
