"""
backend/routes/admin_tickets.py
--------------------------------
Admin-only CRUD and review endpoints for support tokens (tickets) and
employee concerns.

Guarantees:
  - Strict RBAC: only users with role="admin" can access these endpoints.
  - Employee Attribution & Anti-Misuse: every ticket shows which employee raised
    it (employee code e.g. EMP-1002, full name, email) so concerns cannot be
    falsified, anonymously blamed, or manipulated.
  - Concern Acknowledgment & Status CRUD: admins can toggle whether a concern
    has been "taken into account" (is_acknowledged), record resolution notes,
    and update ticket status (open -> in_progress -> resolved -> closed).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import require_admin
from db.database import get_db
from db.models import EscalationEvent, Ticket, TicketPriority, TicketStatus, User

router = APIRouter(prefix="/admin/tickets", tags=["admin-tickets"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

def format_employee_code(user: User | None) -> str:
    if not user:
        return "SYSTEM"
    prefix = "ADM" if user.role.value == "admin" else "EMP"
    return f"{prefix}-{1000 + user.id}"


class EmployeeSummary(BaseModel):
    id: int
    employee_code: str
    name: str
    email: str
    role: str


class EscalationEventSummary(BaseModel):
    id: int
    question: str
    reason: str | None
    created_at: str


class TicketAdminItem(BaseModel):
    id: int
    ticket_id: str
    title: str
    description: str
    priority: Literal["low", "medium", "high"]
    status: Literal["open", "in_progress", "resolved", "closed"]
    is_acknowledged: bool
    acknowledged_at: str | None
    admin_notes: str | None
    admin_response: str | None
    created_at: str
    employee: EmployeeSummary | None
    acknowledged_by: EmployeeSummary | None
    escalation_events: list[EscalationEventSummary]


class TicketListAdminResponse(BaseModel):
    tickets: list[TicketAdminItem]
    total: int
    open_count: int
    in_progress_count: int
    resolved_count: int
    acknowledged_count: int


class TicketAdminUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"] | None = None
    is_acknowledged: bool | None = None
    admin_notes: str | None = None
    admin_response: str | None = None
    priority: Literal["low", "medium", "high"] | None = None


class TicketAdminCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=2000)
    priority: Literal["low", "medium", "high"] = "medium"
    employee_email: str | None = None
    is_acknowledged: bool = False
    admin_notes: str | None = None
    admin_response: str | None = None


def _to_admin_item(ticket: Ticket) -> TicketAdminItem:
    employee_summary = None
    if ticket.created_by:
        employee_summary = EmployeeSummary(
            id=ticket.created_by.id,
            employee_code=format_employee_code(ticket.created_by),
            name=ticket.created_by.name,
            email=ticket.created_by.email,
            role=ticket.created_by.role.value,
        )

    acknowledged_by_summary = None
    if ticket.acknowledged_by:
        acknowledged_by_summary = EmployeeSummary(
            id=ticket.acknowledged_by.id,
            employee_code=format_employee_code(ticket.acknowledged_by),
            name=ticket.acknowledged_by.name,
            email=ticket.acknowledged_by.email,
            role=ticket.acknowledged_by.role.value,
        )

    escalations = [
        EscalationEventSummary(
            id=ev.id,
            question=ev.question,
            reason=ev.reason,
            created_at=ev.created_at.isoformat(),
        )
        for ev in (ticket.escalation_events or [])
    ]

    return TicketAdminItem(
        id=ticket.id,
        ticket_id=ticket.ticket_id,
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority.value,
        status=ticket.status.value,
        is_acknowledged=ticket.is_acknowledged,
        acknowledged_at=ticket.acknowledged_at.isoformat() if ticket.acknowledged_at else None,
        admin_notes=ticket.admin_notes,
        admin_response=ticket.admin_response,
        created_at=ticket.created_at.isoformat(),
        employee=employee_summary,
        acknowledged_by=acknowledged_by_summary,
        escalation_events=escalations,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=TicketListAdminResponse)
async def list_admin_tickets(
    status_filter: str | None = Query(default=None, alias="status"),
    acknowledged: bool | None = Query(default=None),
    priority_filter: str | None = Query(default=None, alias="priority"),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TicketListAdminResponse:
    """
    List all tickets/tokens with full employee attribution and concern details.
    Includes metric counts for quick dashboard stat widgets.
    """
    stmt = (
        select(Ticket)
        .options(
            selectinload(Ticket.created_by),
            selectinload(Ticket.acknowledged_by),
            selectinload(Ticket.escalation_events),
        )
        .order_by(Ticket.created_at.desc())
    )

    if status_filter and status_filter.lower() != "all":
        try:
            stmt = stmt.where(Ticket.status == TicketStatus(status_filter.lower()))
        except ValueError:
            pass

    if acknowledged is not None:
        stmt = stmt.where(Ticket.is_acknowledged.is_(acknowledged))

    if priority_filter and priority_filter.lower() != "all":
        try:
            stmt = stmt.where(Ticket.priority == TicketPriority(priority_filter.lower()))
        except ValueError:
            pass

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.outerjoin(Ticket.created_by).where(
            or_(
                Ticket.ticket_id.ilike(term),
                Ticket.title.ilike(term),
                Ticket.description.ilike(term),
                User.name.ilike(term),
                User.email.ilike(term),
            )
        )

    rows = (await db.execute(stmt)).scalars().all()

    # Calculate overall counts across all tickets
    all_tickets_stmt = select(Ticket)
    all_tickets = (await db.execute(all_tickets_stmt)).scalars().all()
    open_cnt = sum(1 for t in all_tickets if t.status == TicketStatus.open)
    in_prog_cnt = sum(1 for t in all_tickets if t.status == TicketStatus.in_progress)
    res_cnt = sum(1 for t in all_tickets if t.status in (TicketStatus.resolved, TicketStatus.closed))
    ack_cnt = sum(1 for t in all_tickets if t.is_acknowledged)

    items = [_to_admin_item(ticket) for ticket in rows]
    return TicketListAdminResponse(
        tickets=items,
        total=len(items),
        open_count=open_cnt,
        in_progress_count=in_prog_cnt,
        resolved_count=res_cnt,
        acknowledged_count=ack_cnt,
    )


@router.post("", response_model=TicketAdminItem, status_code=status.HTTP_201_CREATED)
async def create_admin_ticket(
    payload: TicketAdminCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TicketAdminItem:
    """Manually create or log an employee concern/ticket as an administrator."""
    ticket_id = f"TKT-{uuid4().hex[:8].upper()}"

    creator_user: User | None = None
    if payload.employee_email:
        creator_user = (
            await db.execute(select(User).where(User.email == payload.employee_email.strip().lower()))
        ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    ticket = Ticket(
        ticket_id=ticket_id,
        title=payload.title,
        description=payload.description,
        priority=TicketPriority(payload.priority),
        status=TicketStatus.open,
        is_acknowledged=payload.is_acknowledged,
        acknowledged_at=now if payload.is_acknowledged else None,
        acknowledged_by_id=admin.id if payload.is_acknowledged else None,
        admin_notes=payload.admin_notes,
        created_by_id=creator_user.id if creator_user else admin.id,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket, ["created_by", "acknowledged_by", "escalation_events"])

    return _to_admin_item(ticket)


@router.patch("/{ticket_id}", response_model=TicketAdminItem)
async def update_admin_ticket(
    ticket_id: str,
    payload: TicketAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TicketAdminItem:
    """
    Update ticket status, toggle whether concern is 'taken into account',
    and record administrative audit notes.
    """
    stmt = (
        select(Ticket)
        .options(
            selectinload(Ticket.created_by),
            selectinload(Ticket.acknowledged_by),
            selectinload(Ticket.escalation_events),
        )
        .where(Ticket.ticket_id == ticket_id)
    )
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id!r} was not found.",
        )

    now = datetime.now(timezone.utc)
    if payload.status is not None:
        ticket.status = TicketStatus(payload.status)

    if payload.priority is not None:
        ticket.priority = TicketPriority(payload.priority)

    if payload.admin_notes is not None:
        ticket.admin_notes = payload.admin_notes

    if payload.admin_response is not None:
        ticket.admin_response = payload.admin_response

    if payload.is_acknowledged is not None:
        ticket.is_acknowledged = payload.is_acknowledged
        if payload.is_acknowledged:
            ticket.acknowledged_at = now
            ticket.acknowledged_by_id = admin.id
            ticket.acknowledged_by = admin
        else:
            ticket.acknowledged_at = None
            ticket.acknowledged_by_id = None
            ticket.acknowledged_by = None

    await db.flush()
    await db.refresh(ticket, ["created_by", "acknowledged_by", "escalation_events"])
    return _to_admin_item(ticket)


@router.delete("/{ticket_id}")
async def delete_admin_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> dict[str, str | bool]:
    """Delete or dismiss a ticket/token (admin only)."""
    ticket = (await db.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id!r} was not found.",
        )

    await db.delete(ticket)
    await db.flush()
    return {"deleted": True, "ticket_id": ticket_id}
