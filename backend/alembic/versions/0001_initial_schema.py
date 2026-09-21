"""
Initial schema — five core tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-21

Tables created:
    users
    documents
    tickets
    feedback
    escalation_events
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id",            sa.Integer(),                           nullable=False),
        sa.Column("name",          sa.String(255),                         nullable=False),
        sa.Column("email",         sa.String(255),                         nullable=False),
        sa.Column("password_hash", sa.Text(),                              nullable=True),
        sa.Column("role",          sa.Enum("employee", "hr_admin", "it_admin", "superuser", name="userrole"), nullable=False),
        sa.Column("is_active",     sa.Boolean(),                           nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True),             nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.create_index("ix_users_role",  "users", ["role"],  unique=False)

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id",             sa.Integer(),                          nullable=False),
        sa.Column("document_id",    sa.String(255),                        nullable=False),
        sa.Column("filename",       sa.String(512),                        nullable=False),
        sa.Column("title",          sa.String(512),                        nullable=True),
        sa.Column("status",         sa.Enum("pending", "ingesting", "ingested", "failed", "deleted", name="documentstatus"), nullable=False),
        sa.Column("chunks_count",   sa.Integer(),                          nullable=True),
        sa.Column("storage_path",   sa.Text(),                             nullable=True),
        sa.Column("uploaded_at",    sa.DateTime(timezone=True),            nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(),                          nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_documents_document_id"),
    )
    op.create_index("ix_documents_document_id", "documents", ["document_id"], unique=False)
    op.create_index("ix_documents_status",      "documents", ["status"],      unique=False)
    op.create_index("ix_documents_uploaded_at", "documents", ["uploaded_at"], unique=False)

    # ── tickets ───────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id",            sa.Integer(),                           nullable=False),
        sa.Column("ticket_id",     sa.String(64),                          nullable=False),
        sa.Column("title",         sa.String(512),                         nullable=False),
        sa.Column("description",   sa.Text(),                              nullable=False),
        sa.Column("priority",      sa.Enum("low", "medium", "high", name="ticketpriority"), nullable=False),
        sa.Column("status",        sa.Enum("open", "in_progress", "resolved", "closed", name="ticketstatus"), nullable=False),
        sa.Column("created_at",    sa.DateTime(timezone=True),             nullable=False),
        sa.Column("created_by_id", sa.Integer(),                           nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", name="uq_tickets_ticket_id"),
    )
    op.create_index("ix_tickets_ticket_id",  "tickets", ["ticket_id"],  unique=False)
    op.create_index("ix_tickets_status",     "tickets", ["status"],     unique=False)
    op.create_index("ix_tickets_created_at", "tickets", ["created_at"], unique=False)

    # ── feedback ──────────────────────────────────────────────────────────────
    op.create_table(
        "feedback",
        sa.Column("id",          sa.Integer(),               nullable=False),
        sa.Column("response_id", sa.String(255),             nullable=True),
        sa.Column("question",    sa.Text(),                  nullable=False),
        sa.Column("rating",      sa.SmallInteger(),          nullable=False),
        sa.Column("comment",     sa.Text(),                  nullable=True),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id",     sa.Integer(),               nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feedback_response_id", "feedback", ["response_id"], unique=False)
    op.create_index("ix_feedback_user_id",     "feedback", ["user_id"],     unique=False)
    op.create_index("ix_feedback_created_at",  "feedback", ["created_at"],  unique=False)
    op.create_index("ix_feedback_rating",      "feedback", ["rating"],      unique=False)

    # ── escalation_events ─────────────────────────────────────────────────────
    op.create_table(
        "escalation_events",
        sa.Column("id",          sa.Integer(),               nullable=False),
        sa.Column("response_id", sa.String(255),             nullable=True),
        sa.Column("question",    sa.Text(),                  nullable=False),
        sa.Column("reason",      sa.String(64),              nullable=True),
        sa.Column("ticket_id",   sa.Integer(),               nullable=True),
        sa.Column("success",     sa.Boolean(),               nullable=False),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalation_events_response_id", "escalation_events", ["response_id"], unique=False)
    op.create_index("ix_escalation_events_ticket_id",   "escalation_events", ["ticket_id"],   unique=False)
    op.create_index("ix_escalation_events_created_at",  "escalation_events", ["created_at"],  unique=False)
    op.create_index("ix_escalation_events_reason",      "escalation_events", ["reason"],      unique=False)


def downgrade() -> None:
    op.drop_table("escalation_events")
    op.drop_table("feedback")
    op.drop_table("tickets")
    op.drop_table("documents")
    op.drop_table("users")

    # Drop custom enum types created for PostgreSQL
    for enum_name in ("userrole", "documentstatus", "ticketpriority", "ticketstatus"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
