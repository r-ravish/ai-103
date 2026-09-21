"""
backend/tests/test_rbac.py
-----------------------------
Tests for role-based access control across the protected routes:

    /chat                      -> employee or admin
    /onboarding/documents      -> admin only
    /onboarding/upload         -> admin only
    /onboarding/documents/{id} (DELETE) -> admin only
    /admin/feedback            -> admin only

Covers: 401 for unauthenticated requests, 403 for authenticated users
without the required role, and 200 for users with the required role.
"""
from __future__ import annotations

import pytest

from tests.conftest import run_async


def _signup(client, email, password="password1234", name="Test User"):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": password})


def _promote_to_admin(db_sessionmaker, email: str) -> None:
    """Directly promote a signed-up user to admin (simulates scripts/create_admin.py)."""
    from sqlalchemy import select
    from db.models import User, UserRole

    async def _promote():
        async with db_sessionmaker() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.role = UserRole.admin
            await session.commit()

    run_async(_promote())


def _make_employee(client, email="employee@company.com"):
    _signup(client, email=email)
    return client


def _make_admin(client, db_sessionmaker, email="admin@company.com"):
    _signup(client, email=email)
    _promote_to_admin(db_sessionmaker, email)
    return client


class _FakeFoundryService:
    def ask(self, question: str) -> dict:
        return {
            "answer": "Employees get 20 days of PTO per year.",
            "citations": [],
            "escalation_required": False,
            "escalation_reason": None,
            "action_taken": False,
            "action_type": None,
            "ticket_id": None,
        }


@pytest.fixture()
def fake_foundry_service(app):
    """Install a fake FoundryAgentService so /chat doesn't need real Azure creds."""
    import app.main as main_module

    previous = main_module.foundry_service
    main_module.foundry_service = _FakeFoundryService()
    yield
    main_module.foundry_service = previous


# ---------------------------------------------------------------------------
# /chat — employee or admin
# ---------------------------------------------------------------------------

def test_chat_requires_authentication(client):
    response = client.post("/chat", json={"question": "What is the leave policy?"})
    assert response.status_code == 401


def test_employee_can_access_chat(client, fake_foundry_service):
    _make_employee(client)
    response = client.post("/chat", json={"question": "What is the leave policy?"})
    assert response.status_code == 200
    assert "answer" in response.json()


def test_admin_can_access_chat(client, fake_foundry_service, db_sessionmaker):
    _make_admin(client, db_sessionmaker)
    response = client.post("/chat", json={"question": "What is the leave policy?"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /onboarding/* — admin only
# ---------------------------------------------------------------------------

def test_onboarding_documents_requires_authentication(client):
    response = client.get("/onboarding/documents")
    assert response.status_code == 401


def test_employee_cannot_access_onboarding_documents(client):
    _make_employee(client)
    response = client.get("/onboarding/documents")
    assert response.status_code == 403


def test_admin_can_access_onboarding_documents(client, db_sessionmaker):
    _make_admin(client, db_sessionmaker)
    response = client.get("/onboarding/documents")
    assert response.status_code == 200
    body = response.json()
    assert body == {"documents": [], "total": 0}


def test_employee_cannot_delete_documents(client):
    _make_employee(client)
    response = client.delete("/onboarding/documents/some-doc")
    assert response.status_code == 403


def test_admin_delete_returns_404_for_unknown_document(client, db_sessionmaker):
    _make_admin(client, db_sessionmaker)
    response = client.delete("/onboarding/documents/does-not-exist")
    assert response.status_code == 404


def test_employee_cannot_upload_documents(client):
    _make_employee(client)
    response = client.post(
        "/onboarding/upload",
        files={"file": ("policy.md", b"# Some policy\ncontent", "text/markdown")},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# /admin/feedback — admin only
# ---------------------------------------------------------------------------

def test_admin_feedback_requires_authentication(client):
    response = client.get("/admin/feedback")
    assert response.status_code == 401


def test_employee_cannot_access_admin_feedback(client):
    _make_employee(client)
    response = client.get("/admin/feedback")
    assert response.status_code == 403


def test_admin_can_access_admin_feedback(client, db_sessionmaker):
    _make_admin(client, db_sessionmaker)
    response = client.get("/admin/feedback")
    assert response.status_code == 200
    assert response.json() == {"feedback": [], "total": 0}
