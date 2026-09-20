"""
backend/routes/tickets.py
--------------------------
Internal ticket creation and lookup routes for Day 3.

Endpoints:
  POST /internal/tickets            – create a new support ticket
  GET  /internal/tickets/{ticket_id} – retrieve a ticket by ID

Storage:
  In-memory dict for Day 3 (replaced by a real DB on Day 4+).
  Data is lost on server restart — intentional for the pilot.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/internal/tickets", tags=["tickets"])

# ---------------------------------------------------------------------------
# In-memory store — replaced by a real DB on Day 4+
# ---------------------------------------------------------------------------
_tickets: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TicketCreate(BaseModel):
    """Payload for creating a new support ticket."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        examples=["Cannot access payslips"],
        description="Short, human-readable summary of the issue.",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        examples=["I have tried logging in three times and keep getting a 403 error."],
        description="Full description of the problem or request.",
    )
    priority: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Ticket priority level. Defaults to 'medium'.",
    )


class TicketResponse(BaseModel):
    """Full representation of a ticket returned after creation or lookup."""

    ticket_id: str
    title: str
    description: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "in_progress", "resolved", "closed"]
    created_at: str


class TicketFound(BaseModel):
    """Response wrapper when a ticket is found by ID."""

    found: bool = True
    ticket: TicketResponse


class TicketNotFound(BaseModel):
    """Response wrapper when a ticket ID does not exist."""

    found: bool = False
    ticket_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(payload: TicketCreate) -> TicketResponse:
    """
    Create a new support ticket.

    Returns the created ticket including its generated ``ticket_id``,
    initial status (``open``), and UTC creation timestamp.
    """
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"

    ticket: dict[str, Any] = {
        "ticket_id": ticket_id,
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _tickets[ticket_id] = ticket
    return TicketResponse(**ticket)


@router.get(
    "/{ticket_id}",
    responses={
        200: {"model": TicketFound, "description": "Ticket found."},
        404: {"model": TicketNotFound, "description": "Ticket not found."},
    },
)
async def get_ticket(ticket_id: str) -> TicketFound | TicketNotFound:
    """
    Retrieve a ticket by its ID.

    Returns ``{"found": true, "ticket": {...}}`` when the ticket exists, or
    ``{"found": false, "ticket_id": "..."}`` with HTTP 404 when it does not.
    """
    ticket = _tickets.get(ticket_id)

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail={"found": False, "ticket_id": ticket_id},
        )

    return TicketFound(ticket=TicketResponse(**ticket))
