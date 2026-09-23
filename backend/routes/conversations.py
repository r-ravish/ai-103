"""
backend/routes/conversations.py
---------------------------------
REST endpoints for managing persisted multi-turn conversation sessions.

Endpoints
─────────
GET    /conversations                    – list all conversations owned by the
                                          authenticated user (newest first).
GET    /conversations/{conversation_id}  – full conversation with all messages.
DELETE /conversations/{conversation_id}  – delete a conversation and its messages.

All endpoints require an authenticated session (employee or admin role).
Users can only access their own conversations; any attempt to access another
user's conversation returns 403 Forbidden.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import require_employee
from db.database import get_db
from db.models import Conversation, ConversationMessage, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ConversationSummary(BaseModel):
    """Lightweight conversation listing entry — no messages."""
    id: int
    title: str | None
    created_at: str
    updated_at: str
    message_count: int


class PersistedMessage(BaseModel):
    """A single message turn as stored in the database."""
    id: int
    role: str
    content: str
    citations: list[dict[str, Any]]
    response_id: str | None
    created_at: str


class ConversationDetail(BaseModel):
    """Full conversation with all message turns."""
    id: int
    title: str | None
    created_at: str
    updated_at: str
    messages: list[PersistedMessage]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _iso(dt) -> str:  # type: ignore[override]
    """Return an ISO-8601 string (always UTC) from a datetime."""
    return dt.isoformat() if dt else ""


def _parse_citations(raw: str | None) -> list[dict[str, Any]]:
    """Safely parse the JSON citations blob stored on assistant messages."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationSummary]:
    """Return all conversations belonging to the authenticated user, newest first."""
    rows = (
        await db.execute(
            select(
                Conversation,
                func.count(ConversationMessage.id).label("message_count"),
            )
            .outerjoin(ConversationMessage, ConversationMessage.conversation_id == Conversation.id)
            .where(Conversation.user_id == user.id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
        )
    ).all()

    return [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=_iso(conv.created_at),
            updated_at=_iso(conv.updated_at),
            message_count=count,
        )
        for conv, count in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetail:
    """Return a specific conversation with all of its messages."""
    conversation = (
        await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
    ).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation.")

    messages = (
        await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.id)
        )
    ).scalars().all()

    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=_iso(conversation.created_at),
        updated_at=_iso(conversation.updated_at),
        messages=[
            PersistedMessage(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                citations=_parse_citations(msg.citations_json),
                response_id=msg.response_id,
                created_at=_iso(msg.created_at),
            )
            for msg in messages
        ],
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(require_employee),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation and all of its messages (CASCADE)."""
    conversation = (
        await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
    ).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this conversation.")

    await db.delete(conversation)
    logger.info("Deleted conversation %s (user=%s)", conversation_id, user.id)
