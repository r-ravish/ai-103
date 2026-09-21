"""
backend/tests/test_tickets.py
--------------------------------
Tickets are persisted in PostgreSQL (db.models.Ticket) instead of an
in-memory dict, so they must survive a backend restart. Since tests use a
shared in-memory SQLite engine across the whole session (see conftest.py),
"restart" is simulated by getting a brand-new DB session — the same
guarantee a real Postgres-backed deployment gives across process restarts.
"""
from __future__ import annotations

from tests.conftest import run_async


def test_create_and_get_ticket_round_trip(client):
    create_response = client.post(
        "/internal/tickets",
        json={"title": "VPN issue", "description": "Cannot connect to VPN", "priority": "high"},
    )
    assert create_response.status_code == 201
    ticket = create_response.json()
    assert ticket["status"] == "open"
    assert ticket["priority"] == "high"

    get_response = client.get(f"/internal/tickets/{ticket['ticket_id']}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["found"] is True
    assert body["ticket"]["ticket_id"] == ticket["ticket_id"]
    assert body["ticket"]["title"] == "VPN issue"


def test_get_unknown_ticket_returns_404(client):
    response = client.get("/internal/tickets/TKT-DOESNOTEXIST")
    assert response.status_code == 404


def test_ticket_created_without_session_has_no_creator(client, db_sessionmaker):
    """
    Simulates the MCP escalation flow, which calls /internal/tickets
    server-to-server with no browser session. created_by must stay NULL
    rather than the request failing.
    """
    from sqlalchemy import select
    from db.models import Ticket

    create_response = client.post(
        "/internal/tickets",
        json={"title": "Anonymous ticket", "description": "No session attached"},
    )
    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticket_id"]

    async def _fetch():
        async with db_sessionmaker() as session:
            return (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    ticket_row = run_async(_fetch())
    assert ticket_row.created_by_id is None


def test_ticket_created_by_authenticated_user_is_attributed(client, db_sessionmaker):
    signup_response = client.post(
        "/auth/signup",
        json={"name": "Grace", "email": "grace@company.com", "password": "password1234"},
    )
    assert signup_response.status_code == 201
    user_id = signup_response.json()["id"]

    create_response = client.post(
        "/internal/tickets",
        json={"title": "Payroll question", "description": "Direct deposit delay"},
    )
    assert create_response.status_code == 201
    ticket_id = create_response.json()["ticket_id"]

    from sqlalchemy import select
    from db.models import Ticket

    async def _fetch():
        async with db_sessionmaker() as session:
            return (await session.execute(select(Ticket).where(Ticket.ticket_id == ticket_id))).scalar_one()

    ticket_row = run_async(_fetch())
    assert ticket_row.created_by_id == user_id
