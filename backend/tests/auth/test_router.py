import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.auth import router as auth_router_module
from app.auth.model import RevokedToken, User
from app.auth.schemas import USER_EXAMPLE, UserData
from app.auth.utils import create_access_token
from app.error import UnauthorizedException

SIGNUP_BODY = {"full_name": "TCG User", "email": "tcg@tcgdigital.com", "password": "Str0ngPass!"}


@pytest.fixture
def logged_in(monkeypatch):
    now = datetime.now(timezone.utc)
    user = User(
        user_id=uuid.uuid4(),
        full_name="TCG User",
        email="tcg@tcgdigital.com",
        password_hash="unused",
        token_version=1,
        created_at=now,
    )
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(RevokedToken, "is_revoked", AsyncMock(return_value=False))
    token = create_access_token(user.email, user.token_version)
    return user, {"Authorization": f"Bearer {token}"}


async def test_signup_returns_201_with_token(client, monkeypatch):
    monkeypatch.setattr(
        auth_router_module, "register_user", AsyncMock(return_value=("token-123", UserData(**USER_EXAMPLE)))
    )

    response = await client.post("/api/auth/signup", json=SIGNUP_BODY)

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"] == "token-123"
    assert body["token_type"] == "bearer"
    assert body["data"]["email"] == USER_EXAMPLE["email"]


async def test_signup_rejects_other_domains(client):
    response = await client.post("/api/auth/signup", json={**SIGNUP_BODY, "email": "tcg@gmail.com"})

    assert response.status_code == 400
    assert "tcgdigital.com" in response.json()["error"]["message"]


async def test_signup_rejects_short_password(client):
    response = await client.post("/api/auth/signup", json={**SIGNUP_BODY, "password": "short"})
    assert response.status_code == 422


async def test_login_uses_form_data(client, monkeypatch):
    authenticate = AsyncMock(return_value=("token-123", UserData(**USER_EXAMPLE)))
    monkeypatch.setattr(auth_router_module, "authenticate_user", authenticate)

    response = await client.post(
        "/api/auth/login", data={"username": "tcg@tcgdigital.com", "password": "Str0ngPass!"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "token-123"
    authenticate.assert_awaited_once_with("tcg@tcgdigital.com", "Str0ngPass!")


async def test_login_rejects_bad_credentials(client, monkeypatch):
    monkeypatch.setattr(
        auth_router_module,
        "authenticate_user",
        AsyncMock(side_effect=UnauthorizedException("Invalid email or password")),
    )

    response = await client.post("/api/auth/login", data={"username": "tcg@tcgdigital.com", "password": "x"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password"


async def test_logout_requires_token(client):
    response = await client.post("/api/auth/logout")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_logout_revokes_current_token(client, monkeypatch, logged_in):
    user, headers = logged_in
    logout = AsyncMock()
    monkeypatch.setattr(auth_router_module, "logout_user", logout)

    response = await client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 200
    logged_out_user, payload = logout.await_args.args
    assert logged_out_user is user and payload.sub == user.email


async def test_revoked_token_is_rejected(client, monkeypatch, logged_in):
    _, headers = logged_in
    monkeypatch.setattr(RevokedToken, "is_revoked", AsyncMock(return_value=True))

    response = await client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 401


async def test_token_from_before_a_password_change_is_rejected(client, logged_in):
    user, headers = logged_in
    user.token_version = 2

    response = await client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 401


async def test_change_password_returns_new_token(client, monkeypatch, logged_in):
    _, headers = logged_in
    monkeypatch.setattr(auth_router_module, "change_password", AsyncMock(return_value="new-token"))

    response = await client.post(
        "/api/auth/change-password",
        json={"old_password": "Str0ngPass!", "new_password": "N3wStr0ngPass!", "confirm_new_password": "N3wStr0ngPass!"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-token"


async def test_change_password_rejects_mismatched_passwords(client, logged_in):
    _, headers = logged_in

    response = await client.post(
        "/api/auth/change-password",
        json={"old_password": "Str0ngPass!", "new_password": "N3wStr0ngPass!", "confirm_new_password": "Other1234!"},
        headers=headers,
    )

    assert response.status_code == 400
    assert "do not match" in response.json()["error"]["message"]
