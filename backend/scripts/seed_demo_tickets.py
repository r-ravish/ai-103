"""
backend/scripts/seed_demo_tickets.py
------------------------------------
Seeds initial demonstration tickets and employee concerns into PostgreSQL
to demonstrate the Admin concern tracking, attribution, and CRUD workflows.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv

load_dotenv(os.path.join(_BACKEND, ".env"))


async def seed_tickets() -> None:
    from sqlalchemy import select
    from db.database import AsyncSessionLocal
    from db.models import EscalationEvent, Ticket, TicketPriority, TicketStatus, User

    async with AsyncSessionLocal() as session:
        # Find admin and employee users
        admin = (await session.execute(select(User).where(User.email == "admin@company.com"))).scalar_one_or_none()
        emp = (await session.execute(select(User).where(User.email == "employee@company.com"))).scalar_one_or_none()
        pilot = (await session.execute(select(User).where(User.email == "pilot@company.com"))).scalar_one_or_none()

        if not admin:
            print("[seed_tickets] Admin user not found, please create admin account first.")
            return

        demo_tickets = [
            {
                "ticket_id": "TKT-C7A412F0",
                "title": "Unclear Parental Leave Policy for Adoptive Parents",
                "description": "The handbook section on Parental Leave currently details biological birth maternity/paternity periods, but does not clarify the leave entitlement and transition duration for adoptive parents.",
                "priority": TicketPriority.high,
                "status": TicketStatus.open,
                "is_acknowledged": False,
                "admin_notes": None,
                "created_by_id": emp.id if emp else None,
            },
            {
                "ticket_id": "TKT-B819E043",
                "title": "Remote Ergonomic Equipment Reimbursement Query",
                "description": "Employee requested clarity whether standing desks purchased from third-party vendors qualify for the $500 home-office stipend or only approved vendors.",
                "priority": TicketPriority.medium,
                "status": TicketStatus.in_progress,
                "is_acknowledged": True,
                "admin_notes": "Reviewed with Finance team. Clarifying amendment drafted for next handbook revision.",
                "created_by_id": emp.id if emp else None,
                "acknowledged_by_id": admin.id,
                "acknowledged_at": datetime.now(timezone.utc),
            },
            {
                "ticket_id": "TKT-F234D9A1",
                "title": "Out-of-Network Emergency Healthcare Protocol",
                "description": "Inquiry regarding pre-authorization exceptions when an employee requires urgent medical care while traveling out-of-state outside provider network.",
                "priority": TicketPriority.high,
                "status": TicketStatus.resolved,
                "is_acknowledged": True,
                "admin_notes": "Added emergency exception guidance to the Benefits & Health Insurance policy guide on page 14.",
                "created_by_id": pilot.id if pilot else (emp.id if emp else None),
                "acknowledged_by_id": admin.id,
                "acknowledged_at": datetime.now(timezone.utc),
            },
        ]

        for item in demo_tickets:
            existing = (
                await session.execute(select(Ticket).where(Ticket.ticket_id == item["ticket_id"]))
            ).scalar_one_or_none()
            if existing is None:
                ticket = Ticket(**item)
                session.add(ticket)
                await session.flush()
                # Also add a linked escalation event for audit
                ev = EscalationEvent(
                    response_id=f"resp_{item['ticket_id']}",
                    question=item["description"][:120],
                    reason="knowledge_gap",
                    ticket_id=ticket.id,
                    success=True,
                )
                session.add(ev)
                print(f"[seed_tickets] Created ticket {item['ticket_id']} - {item['title']}")
            else:
                print(f"[seed_tickets] Ticket {item['ticket_id']} already exists, skipping.")

        await session.commit()
        print("[seed_tickets] Done.")


if __name__ == "__main__":
    asyncio.run(seed_tickets())
