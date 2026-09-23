"""
Add conversation memory tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-22

Tables created:
    conversations          -- per-user chat sessions
    conversation_messages  -- individual user/assistant turns with citation JSON
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── conversations ──────────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id",               sa.Integer(),               nullable=False),
        sa.Column("user_id",          sa.Integer(),               nullable=False),
        sa.Column("title",            sa.String(512),             nullable=True),
        sa.Column("last_response_id", sa.String(255),             nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at",       sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conversations_user_id",    "conversations", ["user_id"])
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])

    # ── conversation_messages ──────────────────────────────────────────────────
    op.create_table(
        "conversation_messages",
        sa.Column("id",              sa.Integer(),  nullable=False),
        sa.Column("conversation_id", sa.Integer(),  nullable=False),
        sa.Column(
            "role",
            sa.Enum("user", "assistant", name="conversationmessagerole"),
            nullable=False,
        ),
        sa.Column("content",        sa.Text(),        nullable=False),
        sa.Column("citations_json", sa.Text(),        nullable=True),
        sa.Column("response_id",    sa.String(255),   nullable=True),
        sa.Column("created_at",     sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_conv_messages_conversation_id", "conversation_messages", ["conversation_id"])
    op.create_index("ix_conv_messages_created_at",      "conversation_messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_conv_messages_created_at",      table_name="conversation_messages")
    op.drop_index("ix_conv_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.execute("DROP TYPE IF EXISTS conversationmessagerole")

    op.drop_index("ix_conversations_updated_at", table_name="conversations")
    op.drop_index("ix_conversations_user_id",    table_name="conversations")
    op.drop_table("conversations")
