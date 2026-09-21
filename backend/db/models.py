"""
backend/db/models.py
---------------------
SQLAlchemy 2.0 ORM models for the Enterprise Knowledge Agent.

Five core entities:
    User            -- employees who will authenticate (auth wired later)
    Document        -- policy documents ingested into Azure AI Search
    Ticket          -- IT/HR support tickets created by the agent or users
    Feedback        -- per-response quality ratings from employees
    EscalationEvent -- audit trail for every automatic escalation

All models use Integer primary keys with a surrogate UUID business key where
the domain expects a human-readable identifier (ticket_id, document_id, etc.).

Relationships are declared with back_populates for bidirectional navigation.
All FKs to users.id are nullable so the models work before auth is wired.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Base ─────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    employee  = "employee"
    hr_admin  = "hr_admin"
    it_admin  = "it_admin"
    superuser = "superuser"


class DocumentStatus(str, enum.Enum):
    pending   = "pending"
    ingesting = "ingesting"
    ingested  = "ingested"
    failed    = "failed"
    deleted   = "deleted"


class TicketPriority(str, enum.Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class TicketStatus(str, enum.Enum):
    open        = "open"
    in_progress = "in_progress"
    resolved    = "resolved"
    closed      = "closed"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    """
    An employee or admin account.

    password_hash is stored here so auth can be wired later without
    a schema migration. The field is nullable until the auth layer exists.
    """
    __tablename__ = "users"

    id            : Mapped[int]           = mapped_column(Integer, primary_key=True, autoincrement=True)
    name          : Mapped[str]           = mapped_column(String(255), nullable=False)
    email         : Mapped[str]           = mapped_column(String(255), nullable=False)
    password_hash : Mapped[str | None]    = mapped_column(Text, nullable=True)
    role          : Mapped[UserRole]      = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False, default=UserRole.employee
    )
    is_active     : Mapped[bool]          = mapped_column(Boolean, nullable=False, default=True)
    created_at    : Mapped[datetime]      = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    documents     : Mapped[list[Document]]       = relationship("Document",        back_populates="uploaded_by")
    tickets       : Mapped[list[Ticket]]         = relationship("Ticket",          back_populates="created_by")
    feedback_list : Mapped[list[Feedback]]       = relationship("Feedback",        back_populates="user")

    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"

class Document(Base):
    """
    A policy document that has been (or is being) ingested into Azure AI Search.

    document_id mirrors the Azure Search document_id / filename stem used in
    the retrieval contract (docs/ingestion-contract.md).
    """
    __tablename__ = "documents"

    id             : Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id    : Mapped[str]            = mapped_column(String(255), nullable=False)
    filename       : Mapped[str]            = mapped_column(String(512), nullable=False)
    title          : Mapped[str | None]     = mapped_column(String(512), nullable=True)
    status         : Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="documentstatus"),
        nullable=False,
        default=DocumentStatus.pending,
    )
    chunks_count   : Mapped[int | None]     = mapped_column(Integer, nullable=True)
    storage_path   : Mapped[str | None]     = mapped_column(Text, nullable=True)
    uploaded_at    : Mapped[datetime]       = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    uploaded_by_id : Mapped[int | None]     = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    uploaded_by : Mapped[User | None] = relationship("User", back_populates="documents")

    __table_args__ = (
        UniqueConstraint("document_id", name="uq_documents_document_id"),
        Index("ix_documents_document_id",  "document_id"),
        Index("ix_documents_status",       "status"),
        Index("ix_documents_uploaded_at",  "uploaded_at"),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} document_id={self.document_id!r} status={self.status}>"

class Ticket(Base):
    """
    A support ticket created by the MCP escalation tool or a user.

    ticket_id (e.g. TKT-A1B2C3D4) is the human-readable business key
    returned by POST /internal/tickets and embedded in agent responses.
    """
    __tablename__ = "tickets"

    id            : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id     : Mapped[str]          = mapped_column(String(64), nullable=False)
    title         : Mapped[str]          = mapped_column(String(512), nullable=False)
    description   : Mapped[str]          = mapped_column(Text, nullable=False)
    priority      : Mapped[TicketPriority] = mapped_column(
        Enum(TicketPriority, name="ticketpriority"),
        nullable=False,
        default=TicketPriority.medium,
    )
    status        : Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticketstatus"),
        nullable=False,
        default=TicketStatus.open,
    )
    created_at    : Mapped[datetime]     = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    created_by_id : Mapped[int | None]   = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    created_by       : Mapped[User | None]              = relationship("User", back_populates="tickets")
    escalation_events: Mapped[list[EscalationEvent]]    = relationship("EscalationEvent", back_populates="ticket")

    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_tickets_ticket_id"),
        Index("ix_tickets_ticket_id",  "ticket_id"),
        Index("ix_tickets_status",     "status"),
        Index("ix_tickets_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} ticket_id={self.ticket_id!r} status={self.status}>"

class Feedback(Base):
    """
    Employee quality rating on a specific agent response.

    response_id matches the Foundry Responses API response.id so feedback
    can be correlated with Foundry traces.
    """
    __tablename__ = "feedback"

    id          : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    response_id : Mapped[str | None]   = mapped_column(String(255), nullable=True)
    question    : Mapped[str]          = mapped_column(Text, nullable=False)
    rating      : Mapped[int]          = mapped_column(SmallInteger, nullable=False)   # 1-5
    comment     : Mapped[str | None]   = mapped_column(Text, nullable=True)
    created_at  : Mapped[datetime]     = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    user_id     : Mapped[int | None]   = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    user : Mapped[User | None] = relationship("User", back_populates="feedback_list")

    __table_args__ = (
        Index("ix_feedback_response_id", "response_id"),
        Index("ix_feedback_user_id",     "user_id"),
        Index("ix_feedback_created_at",  "created_at"),
        Index("ix_feedback_rating",      "rating"),
    )

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} rating={self.rating} response_id={self.response_id!r}>"

class EscalationEvent(Base):
    """
    Audit record for every automatic knowledge-gap escalation.

    Created by foundry_agent.py when _detect_knowledge_gap() returns True
    and a support ticket is requested via MCP.
    """
    __tablename__ = "escalation_events"

    id          : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    response_id : Mapped[str | None] = mapped_column(String(255), nullable=True)
    question    : Mapped[str]        = mapped_column(Text, nullable=False)
    reason      : Mapped[str | None] = mapped_column(String(64), nullable=True)   # e.g. "knowledge_gap", "out_of_scope"
    ticket_id   : Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True
    )
    success     : Mapped[bool]       = mapped_column(Boolean, nullable=False, default=False)
    created_at  : Mapped[datetime]   = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # Relationships
    ticket : Mapped[Ticket | None] = relationship("Ticket", back_populates="escalation_events")

    __table_args__ = (
        Index("ix_escalation_events_response_id", "response_id"),
        Index("ix_escalation_events_ticket_id",   "ticket_id"),
        Index("ix_escalation_events_created_at",  "created_at"),
        Index("ix_escalation_events_reason",      "reason"),
    )

    def __repr__(self) -> str:
        return (
            f"<EscalationEvent id={self.id} reason={self.reason!r} success={self.success}>"        )
