"""
backend/tests/test_conversations.py
--------------------------------------
Integration tests for the persistent multi-turn conversation memory feature.

Covers:
  - POST /chat creates a new conversation and returns conversation_id.
  - Second POST /chat with that conversation_id continues the same conversation.
  - GET /conversations returns the user's conversations list.
  - GET /conversations/{id} returns all messages.
  - Cross-user access is rejected with 403.
  - DELETE /conversations/{id} removes the conversation; subsequent GET → 404.
  - Unauthenticated requests return 401.
"""
from __future__ import annotations

import pytest

from tests.conftest import run_async


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signup(client, email, password="password1234", name="Test User"):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": password})


def _login(client, email, password="password1234"):
    return client.post("/auth/login", json={"email": email, "password": password})


def _promote_to_admin(db_sessionmaker, email: str) -> None:
    from sqlalchemy import select
    from db.models import User, UserRole

    async def _promote():
        async with db_sessionmaker() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.role = UserRole.admin
            await session.commit()

    run_async(_promote())


class _FakeFoundryService:
    """Fake Foundry service — no real Azure calls needed."""

    call_count = 0

    def ask(self, question: str, *, previous_response_id: str | None = None) -> dict:
        _FakeFoundryService.call_count += 1
        return {
            "answer": f"Answer #{_FakeFoundryService.call_count} to: {question!r}",
            "citations": [],
            "escalation_required": False,
            "escalation_reason": None,
            "action_taken": False,
            "action_type": None,
            "ticket_id": None,
            "response_id": f"resp-{_FakeFoundryService.call_count:04d}",
        }


@pytest.fixture()
def fake_foundry_service(app):
    import app.main as main_module
    _FakeFoundryService.call_count = 0
    previous = main_module.foundry_service
    main_module.foundry_service = _FakeFoundryService()
    yield
    main_module.foundry_service = previous


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestChatCreatesConversation:
    """POST /chat must create a new conversation and return conversation_id."""

    def test_first_chat_returns_conversation_id(self, client, fake_foundry_service):
        _signup(client, "chat_conv@example.com")
        _login(client, "chat_conv@example.com")

        resp = client.post("/chat", json={"question": "What is the leave policy?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], int)
        assert data["conversation_id"] > 0

    def test_second_chat_continues_conversation(self, client, fake_foundry_service):
        _signup(client, "chat_cont@example.com")
        _login(client, "chat_cont@example.com")

        # First turn — creates new conversation
        r1 = client.post("/chat", json={"question": "What is the WFH policy?"})
        assert r1.status_code == 200
        conv_id = r1.json()["conversation_id"]

        # Second turn — continues the same conversation
        r2 = client.post("/chat", json={
            "question": "Can I work remotely full-time?",
            "conversation_id": conv_id,
        })
        assert r2.status_code == 200
        assert r2.json()["conversation_id"] == conv_id

    def test_chat_requires_auth(self, client, fake_foundry_service):
        resp = client.post("/chat", json={"question": "What is the leave policy?"})
        assert resp.status_code == 401


class TestListConversations:
    """GET /conversations must return the user's conversations in descending order."""

    def test_list_returns_conversations(self, client, fake_foundry_service):
        _signup(client, "list_conv@example.com")
        _login(client, "list_conv@example.com")

        # Create two conversations
        client.post("/chat", json={"question": "Question A"})
        client.post("/chat", json={"question": "Question B"})

        resp = client.get("/conversations")
        assert resp.status_code == 200
        convs = resp.json()
        assert len(convs) == 2
        # Newest first
        assert convs[0]["updated_at"] >= convs[1]["updated_at"]

    def test_list_requires_auth(self, client):
        resp = client.get("/conversations")
        assert resp.status_code == 401

    def test_list_is_user_scoped(self, client, db_sessionmaker, fake_foundry_service):
        _signup(client, "userA_list@example.com")
        _login(client, "userA_list@example.com")
        client.post("/chat", json={"question": "User A question"})

        # Log in as a different user
        _signup(client, "userB_list@example.com")
        _login(client, "userB_list@example.com")

        resp = client.get("/conversations")
        assert resp.status_code == 200
        # User B should see 0 conversations (User A's conversation is not visible)
        assert resp.json() == []


class TestGetConversation:
    """GET /conversations/{id} must return the conversation with all messages."""

    def test_get_conversation_with_messages(self, client, fake_foundry_service):
        _signup(client, "get_conv@example.com")
        _login(client, "get_conv@example.com")

        r = client.post("/chat", json={"question": "What is the PTO policy?"})
        conv_id = r.json()["conversation_id"]

        resp = client.get(f"/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == conv_id
        # Should have 2 messages: user + assistant
        assert len(data["messages"]) == 2
        roles = [m["role"] for m in data["messages"]]
        assert roles == ["user", "assistant"]

    def test_get_conversation_404_for_missing(self, client):
        _signup(client, "get_404@example.com")
        _login(client, "get_404@example.com")

        resp = client.get("/conversations/999999")
        assert resp.status_code == 404

    def test_get_conversation_403_cross_user(self, client, fake_foundry_service):
        # User A creates a conversation
        _signup(client, "owner_conv@example.com")
        _login(client, "owner_conv@example.com")
        r = client.post("/chat", json={"question": "Private question"})
        conv_id = r.json()["conversation_id"]

        # User B tries to access it
        _signup(client, "intruder_conv@example.com")
        _login(client, "intruder_conv@example.com")
        resp = client.get(f"/conversations/{conv_id}")
        assert resp.status_code == 403

    def test_get_conversation_requires_auth(self, client, fake_foundry_service):
        # Create a conversation first
        _signup(client, "auth_get@example.com")
        _login(client, "auth_get@example.com")
        r = client.post("/chat", json={"question": "Auth test"})
        conv_id = r.json()["conversation_id"]

        # Clear cookies (simulate unauthenticated)
        client.cookies.clear()
        resp = client.get(f"/conversations/{conv_id}")
        assert resp.status_code == 401


class TestDeleteConversation:
    """DELETE /conversations/{id} must remove the conversation for its owner."""

    def test_delete_removes_conversation(self, client, fake_foundry_service):
        _signup(client, "del_conv@example.com")
        _login(client, "del_conv@example.com")

        r = client.post("/chat", json={"question": "To be deleted"})
        conv_id = r.json()["conversation_id"]

        del_resp = client.delete(f"/conversations/{conv_id}")
        assert del_resp.status_code == 204

        # Subsequent GET should 404
        get_resp = client.get(f"/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_delete_403_cross_user(self, client, fake_foundry_service):
        _signup(client, "del_owner@example.com")
        _login(client, "del_owner@example.com")
        r = client.post("/chat", json={"question": "My question"})
        conv_id = r.json()["conversation_id"]

        _signup(client, "del_intruder@example.com")
        _login(client, "del_intruder@example.com")
        resp = client.delete(f"/conversations/{conv_id}")
        assert resp.status_code == 403

    def test_delete_requires_auth(self, client, fake_foundry_service):
        _signup(client, "del_auth@example.com")
        _login(client, "del_auth@example.com")
        r = client.post("/chat", json={"question": "Will be gone"})
        conv_id = r.json()["conversation_id"]

        client.cookies.clear()
        resp = client.delete(f"/conversations/{conv_id}")
        assert resp.status_code == 401


class TestContinuationOwnership:
    """Trying to continue another user's conversation via POST /chat must 403."""

    def test_continue_cross_user_conversation_403(self, client, fake_foundry_service):
        _signup(client, "a_cont@example.com")
        _login(client, "a_cont@example.com")
        r = client.post("/chat", json={"question": "Owner message"})
        conv_id = r.json()["conversation_id"]

        _signup(client, "b_cont@example.com")
        _login(client, "b_cont@example.com")
        resp = client.post("/chat", json={
            "question": "Intruder message",
            "conversation_id": conv_id,
        })
        assert resp.status_code == 403
