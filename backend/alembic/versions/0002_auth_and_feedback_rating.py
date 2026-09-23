"""
Auth + RBAC foundation, feedback rating rework.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-21

Changes:
    * users.role       -- collapse ("employee", "hr_admin", "it_admin",
                           "superuser") down to the two roles the RBAC layer
                           actually enforces: ("employee", "admin").
                           hr_admin/it_admin/superuser all map to "admin".
    * feedback.rating   -- was a 1-5 smallint; the thumbs up/down contract
                           (POST /feedback) uses "up"/"down" instead.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users.role: userrole(employee, hr_admin, it_admin, superuser) → userrole(employee, admin)
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute("CREATE TYPE userrole AS ENUM ('employee', 'admin')")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole
        USING (CASE WHEN role::text = 'employee' THEN 'employee' ELSE 'admin' END)::userrole
        """
    )
    op.execute("DROP TYPE userrole_old")

    # ── feedback.rating: smallint (1-5) → feedbackrating enum (up/down)
    op.execute("CREATE TYPE feedbackrating AS ENUM ('up', 'down')")
    op.execute(
        """
        ALTER TABLE feedback
        ALTER COLUMN rating TYPE feedbackrating
        USING (CASE WHEN rating >= 3 THEN 'up' ELSE 'down' END)::feedbackrating
        """
    )


def downgrade() -> None:
    # ── feedback.rating back to smallint
    op.execute(
        """
        ALTER TABLE feedback
        ALTER COLUMN rating TYPE smallint
        USING (CASE WHEN rating::text = 'up' THEN 5 ELSE 1 END)
        """
    )
    op.execute("DROP TYPE feedbackrating")

    # ── users.role back to the original four-value enum
    op.execute("ALTER TYPE userrole RENAME TO userrole_new")
    op.execute("CREATE TYPE userrole AS ENUM ('employee', 'hr_admin', 'it_admin', 'superuser')")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole
        USING (CASE WHEN role::text = 'employee' THEN 'employee' ELSE 'hr_admin' END)::userrole
        """
    )
    op.execute("DROP TYPE userrole_new")
