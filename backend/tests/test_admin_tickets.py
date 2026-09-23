"""
backend/tests/test_admin_tickets.py
------------------------------------
Tests for Admin Ticket and Concern Management:
  - RBAC: 401 unauthenticated, 403 employee, 200 admin.
  - Employee Attribution & Anti-Misuse: verifies creator details (employee code,
    name, email) are accurately attached.
  - Concern CRUD: toggling 'taken into account' (is_acknowledged), updating
    status (open -> in_progress -> resolved), editing admin notes.
  - Manual creation and deletion.
"""
from __future__ import annotations

from tests.conftest import run_async


def _signup(client, email: str, name: str = "Test User", password: str = "password1234"):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": password})


def _promote_to_admin(db_sessionmaker, email: str) -> None:
    from sqlalchemy import select
    from db.models import User, UserRole

    async def _promote():
        async with db_sessionmaker() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.role = UserRole.admin
            await session.commit()

    run_async(_promote())


def test_admin_tickets_requires_authentication(client):
    response = client.get("/admin/tickets")
    assert response.status_code == 401


def test_employee_cannot_access_admin_tickets(client):
    _signup(client, email="employee_alice@company.com", name="Alice Employee")
    response = client.get("/admin/tickets")
    assert response.status_code == 403


def test_admin_can_list_tickets_with_attribution(client, db_sessionmaker):
    # 1. Sign up employee and have them create a ticket
    _signup(client, email="employee_bob@company.com", name="Bob Employee")
    ticket_res = client.post(
        "/internal/tickets",
        json={
            "title": "Need dental insurance policy details",
            "description": "How do I claim out-of-network dental expenses?",
            "priority": "medium",
        },
    )
    assert ticket_res.status_code == 201
    ticket_id = ticket_res.json()["ticket_id"]

    # 2. Log in as admin
    client.post("/auth/logout")
    _signup(client, email="admin_carol@company.com", name="Carol Admin")
    _promote_to_admin(db_sessionmaker, "admin_carol@company.com")
    # Re-login to refresh admin token
    login_res = client.post(
        "/auth/login",
        json={"email": "admin_carol@company.com", "password": "password1234"},
    )
    assert login_res.status_code == 200

    # 3. List tickets as admin
    res = client.get("/admin/tickets")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert "open_count" in data

    # Find Bob's ticket
    found = next((t for t in data["tickets"] if t["ticket_id"] == ticket_id), None)
    assert found is not None
    assert found["title"] == "Need dental insurance policy details"
    assert found["description"] == "How do I claim out-of-network dental expenses?"
    assert found["is_acknowledged"] is False
    assert found["employee"] is not None
    assert found["employee"]["email"] == "employee_bob@company.com"
    assert found["employee"]["name"] == "Bob Employee"
    assert found["employee"]["employee_code"].startswith("EMP-")


def test_admin_take_into_account_and_update_status(client, db_sessionmaker):
    # Admin signs up
    _signup(client, email="admin_dan@company.com", name="Dan Admin")
    _promote_to_admin(db_sessionmaker, "admin_dan@company.com")
    client.post("/auth/login", json={"email": "admin_dan@company.com", "password": "password1234"})

    # Create a ticket
    ticket_res = client.post(
        "/admin/tickets",
        json={
            "title": "Unclear WFH reimbursement limits",
            "description": "The handbook mentions $500/year but HR said $300.",
            "priority": "high",
        },
    )
    assert ticket_res.status_code == 201
    ticket_id = ticket_res.json()["ticket_id"]

    # Admin takes concern into account (is_acknowledged = True) and adds note
    patch_res = client.patch(
        f"/admin/tickets/{ticket_id}",
        json={
            "is_acknowledged": True,
            "status": "in_progress",
            "admin_notes": "Reviewed with Finance; clarifying policy document in progress.",
        },
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["is_acknowledged"] is True
    assert updated["status"] == "in_progress"
    assert updated["acknowledged_at"] is not None
    assert updated["acknowledged_by"]["name"] == "Dan Admin"
    assert updated["admin_notes"] == "Reviewed with Finance; clarifying policy document in progress."

    # Now mark as resolved
    resolve_res = client.patch(
        f"/admin/tickets/{ticket_id}",
        json={"status": "resolved", "admin_notes": "Policy doc updated to reflect $500."},
    )
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"


def test_admin_delete_ticket(client, db_sessionmaker):
    # Admin signs up
    _signup(client, email="admin_eve@company.com", name="Eve Admin")
    _promote_to_admin(db_sessionmaker, "admin_eve@company.com")
    client.post("/auth/login", json={"email": "admin_eve@company.com", "password": "password1234"})

    # Create a ticket
    ticket_res = client.post(
        "/admin/tickets",
        json={"title": "Spam test ticket", "description": "Invalid test"},
    )
    assert ticket_res.status_code == 201
    ticket_id = ticket_res.json()["ticket_id"]

    # Delete ticket
    del_res = client.delete(f"/admin/tickets/{ticket_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True

    # Check that it is gone
    get_res = client.get(f"/internal/tickets/{ticket_id}")
    assert get_res.status_code == 404
