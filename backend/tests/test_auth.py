"""
backend/tests/test_auth.py
-----------------------------
Tests for POST /auth/signup, POST /auth/login, POST /auth/logout, and
GET /auth/me.
"""
from __future__ import annotations


def _signup(client, email="alice@company.com", password="correct-password", name="Alice"):
    return client.post("/auth/signup", json={"name": name, "email": email, "password": password})


def test_signup_creates_employee_by_default(client):
    response = _signup(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@company.com"
    assert body["role"] == "employee"
    assert "password" not in body
    assert "password_hash" not in body

    # Signup also logs the user in via an HttpOnly cookie.
    assert "access_token" in response.cookies


def test_signup_cannot_request_admin_role(client):
    # The SignupRequest schema has no "role" field at all — a client trying
    # to smuggle role="admin" into the payload is ignored, and the account
    # is still created as "employee".
    response = client.post(
        "/auth/signup",
        json={
            "name": "Wannabe Admin",
            "email": "wannabe@company.com",
            "password": "correct-password",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "employee"


def test_signup_rejects_duplicate_email(client):
    first = _signup(client, email="bob@company.com")
    assert first.status_code == 201

    second = _signup(client, email="bob@company.com")
    assert second.status_code == 400


def test_login_with_valid_credentials_sets_session_cookie(client):
    _signup(client, email="carol@company.com", password="s3cur3-pass!")

    response = client.post(
        "/auth/login",
        json={"email": "carol@company.com", "password": "s3cur3-pass!"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "carol@company.com"
    assert "access_token" in response.cookies


def test_login_with_invalid_password_returns_401(client):
    _signup(client, email="dave@company.com", password="right-password")

    response = client.post(
        "/auth/login",
        json={"email": "dave@company.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_login_with_unknown_email_returns_401(client):
    response = client.post(
        "/auth/login",
        json={"email": "nobody@company.com", "password": "whatever123"},
    )
    assert response.status_code == 401


def test_logout_clears_session(client):
    _signup(client, email="erin@company.com", password="another-password")

    me_before = client.get("/auth/me")
    assert me_before.status_code == 200

    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_after = client.get("/auth/me")
    assert me_after.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_when_authenticated(client):
    _signup(client, email="frank@company.com", password="password1234")

    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "frank@company.com"
    assert body["role"] == "employee"
