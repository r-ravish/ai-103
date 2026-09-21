"""
backend/routes/feedback.py
----------------------------
Persisted feedback on chat responses.

Endpoints
─────────
POST /feedback         — record a thumbs up/down rating for a chat response
GET  /admin/feedback   — (admin only) list persisted feedback for the dashboard

Feedback submission itself does not require a specific role — any logged-in
(or, during the frontend transition, anonymous) user can rate a response.
When a session is present, the feedback is attributed to that user.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user_optional, require_admin
from db.database import get_db
from db.models import Feedback, FeedbackRating, User

router = APIRouter(tags=["feedback"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FeedbackCreate(BaseModel):
    response_id: str = Field(..., min_length=1, max_length=255)
    question: str = Field(..., min_length=1)
    rating: str = Field(..., description="'up' or 'down'")
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    id: int
    response_id: str | None
    question: str
    rating: str
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackResponse]
    total: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback on a chat response",
)
async def submit_feedback(
    payload: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> FeedbackResponse:
    """Persist a thumbs up/down rating. Returns 400 if rating is not 'up'/'down'."""
    rating_value = payload.rating.strip().lower()
    if rating_value not in {r.value for r in FeedbackRating}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rating must be either 'up' or 'down'.",
        )

    feedback = Feedback(
        response_id=payload.response_id,
        question=payload.question,
        rating=FeedbackRating(rating_value),
        comment=payload.comment,
        user_id=user.id if user else None,
    )
    db.add(feedback)
    await db.flush()
    await db.refresh(feedback)

    return FeedbackResponse(
        id=feedback.id,
        response_id=feedback.response_id,
        question=feedback.question,
        rating=feedback.rating.value,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


@router.get(
    "/admin/feedback",
    response_model=FeedbackListResponse,
    summary="List all persisted feedback (admin only)",
)
async def list_feedback(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> FeedbackListResponse:
    """Return all feedback rows, most recent first, for the admin dashboard."""
    rows = (
        await db.execute(select(Feedback).order_by(Feedback.created_at.desc()))
    ).scalars().all()

    items = [
        FeedbackResponse(
            id=row.id,
            response_id=row.response_id,
            question=row.question,
            rating=row.rating.value,
            comment=row.comment,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return FeedbackListResponse(feedback=items, total=len(items))
