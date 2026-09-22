"""
backend/routes/tickets.py
--------------------------
Internal ticket creation and lookup routes.

Endpoints:
  POST /internal/tickets            – create a new support ticket
  GET  /internal/tickets/{ticket_id} – retrieve a ticket by ID

Storage:
  PostgreSQL (db.models.Ticket) — tickets now survive backend restarts,
  container restarts, and deployments.

These endpoints are called both by the MCP server (create_support_ticket /
get_support_ticket tools, server-to-server, no browser session) and — once
the frontend is wired up — directly by authenticated employees. created_by
is populated from the session when one is present, and stays NULL for the
unauthenticated MCP flow so escalation-triggered tickets keep working.
"""
from __future__ import annotations

from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user_optional
from db.database import get_db
from db.models import Ticket, TicketPriority, TicketStatus, User

router = APIRouter(prefix="/internal/tickets", tags=["tickets"])


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
    admin_response: str | None
    created_at: str


class TicketFound(BaseModel):
    """Response wrapper when a ticket is found by ID."""

    found: bool = True
    ticket: TicketResponse


class TicketNotFound(BaseModel):
    """Response wrapper when a ticket ID does not exist."""

    found: bool = False
    ticket_id: str


def _to_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.ticket_id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority.value,
        status=ticket.status.value,
        admin_response=ticket.admin_response,
        created_at=ticket.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> TicketResponse:
    """
    Create a new support ticket, persisted in PostgreSQL.

    Returns the created ticket including its generated ``ticket_id``,
    initial status (``open``), and UTC creation timestamp. If the request
    carries a valid session cookie, the ticket's created_by is set to that
    user; otherwise it stays NULL (e.g. the MCP escalation flow).
    """
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"

    ticket = Ticket(
        ticket_id=ticket_id,
        title=payload.title,
        description=payload.description,
        priority=TicketPriority(payload.priority),
        status=TicketStatus.open,
        created_by_id=user.id if user else None,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    return _to_response(ticket)


@router.get(
    "/{ticket_id}",
    responses={
        200: {"model": TicketFound, "description": "Ticket found."},
        404: {"model": TicketNotFound, "description": "Ticket not found."},
    },
)
async def get_ticket(ticket_id: str, db: AsyncSession = Depends(get_db)) -> TicketFound | TicketNotFound:
    """
    Retrieve a ticket by its ID.

    Returns ``{"found": true, "ticket": {...}}`` when the ticket exists, or
    ``{"found": false, "ticket_id": "..."}`` with HTTP 404 when it does not.
    """
    ticket = (await db.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail={"found": False, "ticket_id": ticket_id},
        )

    return TicketFound(ticket=_to_response(ticket))
