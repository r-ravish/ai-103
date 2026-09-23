"""
backend/tests/test_feedback.py
---------------------------------
Tests for POST /feedback and GET /admin/feedback.
"""
from __future__ import annotations

from tests.conftest import run_async


def _promote_to_admin(db_sessionmaker, email: str) -> None:
    from sqlalchemy import select
    from db.models import User, UserRole

    async def _promote():
        async with db_sessionmaker() as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            user.role = UserRole.admin
            await session.commit()

    run_async(_promote())


def test_submit_feedback_with_valid_rating(client):
    response = client.post(
        "/feedback",
        json={
            "response_id": "abc123",
            "question": "What is the leave policy?",
            "rating": "up",
            "comment": "Helpful answer",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["rating"] == "up"
    assert body["comment"] == "Helpful answer"


def test_submit_feedback_without_comment_is_optional(client):
    response = client.post(
        "/feedback",
        json={"response_id": "def456", "question": "What is the WFH policy?", "rating": "down"},
    )
    assert response.status_code == 201
    assert response.json()["comment"] is None


def test_submit_feedback_rejects_invalid_rating(client):
    response = client.post(
        "/feedback",
        json={"response_id": "ghi789", "question": "What is the leave policy?", "rating": "meh"},
    )
    assert response.status_code == 400


def test_admin_feedback_endpoint_requires_admin(client):
    client.post("/auth/signup", json={"name": "Henry", "email": "henry@company.com", "password": "password1234"})
    response = client.get("/admin/feedback")
    assert response.status_code == 403


def test_admin_can_list_persisted_feedback(client, db_sessionmaker):
    client.post(
        "/feedback",
        json={"response_id": "abc123", "question": "What is the leave policy?", "rating": "up"},
    )
    client.post("/auth/signup", json={"name": "Ivy", "email": "ivy@company.com", "password": "password1234"})
    _promote_to_admin(db_sessionmaker, "ivy@company.com")

    response = client.get("/admin/feedback")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["feedback"][0]["response_id"] == "abc123"
