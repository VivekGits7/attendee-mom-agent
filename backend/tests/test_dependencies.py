import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.auth.model import RevokedToken, User
from app.auth.utils import create_access_token
from app.meeting import router as meeting_router_module


@pytest.fixture
def no_meetings(monkeypatch):
    monkeypatch.setattr(meeting_router_module, "list_meetings", AsyncMock(return_value=([], 0)))


@pytest.fixture
def bearer_headers(monkeypatch):
    user = User(
        user_id=uuid.uuid4(),
        full_name="TCG User",
        email="tcg@tcgdigital.com",
        password_hash="unused",
        token_version=0,
        created_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=user))
    monkeypatch.setattr(RevokedToken, "is_revoked", AsyncMock(return_value=False))
    return {"Authorization": f"Bearer {create_access_token(user.email, user.token_version)}"}


async def test_meetings_accept_a_logged_in_user(client, no_meetings, bearer_headers):
    response = await client.get("/api/meetings", headers=bearer_headers)
    assert response.status_code == 200


async def test_meetings_still_accept_the_api_key(client, no_meetings, api_headers):
    response = await client.get("/api/meetings", headers=api_headers)
    assert response.status_code == 200


async def test_meetings_reject_a_revoked_token(client, no_meetings, bearer_headers, monkeypatch):
    monkeypatch.setattr(RevokedToken, "is_revoked", AsyncMock(return_value=True))

    response = await client.get("/api/meetings", headers=bearer_headers)

    assert response.status_code == 401


async def test_meetings_reject_a_forged_token(client, no_meetings):
    response = await client.get("/api/meetings", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_meetings_ask_for_login_without_credentials(client, no_meetings):
    response = await client.get("/api/meetings")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Please log in to continue"


async def test_meetings_reject_a_wrong_api_key(client, no_meetings):
    response = await client.get("/api/meetings", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid or missing API key"


@pytest.mark.parametrize("token", [None, "", 123, {"token": "x"}])
async def test_authenticate_ws_rejects_missing_token(token):
    from app.dependencies import authenticate_ws

    assert await authenticate_ws(token) is None


async def test_authenticate_ws_accepts_valid_token_and_rejects_ended_session(bearer_headers, monkeypatch):
    from app.dependencies import authenticate_ws

    token = bearer_headers["Authorization"].removeprefix("Bearer ")
    user = await authenticate_ws(token)
    assert user is not None and user.email == "tcg@tcgdigital.com"

    monkeypatch.setattr(RevokedToken, "is_revoked", AsyncMock(return_value=True))
    assert await authenticate_ws(token) is None
    assert await authenticate_ws("not-a-jwt") is None
