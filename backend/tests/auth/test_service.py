import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.auth import service as auth_service
from app.auth.model import RevokedToken, User
from app.auth.schemas import ChangePasswordRequest, SignupRequest, TokenPayload
from app.auth.utils import decode_access_token, hash_password, verify_password
from app.error import BadRequestException, ConflictException, UnauthorizedException

PASSWORD = "Str0ngPass!"
PASSWORD_HASH = hash_password(PASSWORD)


def make_user(**overrides) -> User:
    now = datetime.now(timezone.utc)
    fields = {
        "user_id": uuid.uuid4(),
        "full_name": "TCG User",
        "email": "tcg@tcgdigital.com",
        "password_hash": PASSWORD_HASH,
        "token_version": 0,
        "last_login_at": now,
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return User(**fields)


def signup_request(email: str = "tcg@tcgdigital.com") -> SignupRequest:
    return SignupRequest(full_name="TCG User", email=email, password=PASSWORD)


@pytest.mark.parametrize(
    "email",
    ["tcg@gmail.com", "tcg@evil-tcgdigital.com", "tcg@tcgdigital.com.evil.com", "tcg@mail.tcgdigital.com"],
)
async def test_register_rejects_emails_outside_the_domain(monkeypatch, email):
    find = AsyncMock()
    monkeypatch.setattr(User, "find_by_email", find)

    with pytest.raises(BadRequestException) as exc:
        await auth_service.register_user(signup_request(email))

    assert "tcgdigital.com" in exc.value.detail
    find.assert_not_awaited()


async def test_register_accepts_uppercase_domain(monkeypatch):
    user = make_user()
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=None))
    create = AsyncMock(return_value=user)
    monkeypatch.setattr(User, "create", create)

    await auth_service.register_user(signup_request("TCG@TCGDigital.com"))

    assert create.await_args.args[1] == "tcg@tcgdigital.com"


async def test_register_rejects_existing_email(monkeypatch):
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=make_user()))

    with pytest.raises(ConflictException):
        await auth_service.register_user(signup_request())


async def test_register_rejects_parallel_signup_race(monkeypatch):
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(User, "create", AsyncMock(return_value=None))

    with pytest.raises(ConflictException):
        await auth_service.register_user(signup_request())


async def test_register_hashes_password_and_returns_token(monkeypatch):
    user = make_user()
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=None))
    create = AsyncMock(return_value=user)
    monkeypatch.setattr(User, "create", create)

    token, data = await auth_service.register_user(signup_request())

    stored_hash = create.await_args.args[2]
    assert stored_hash != PASSWORD and verify_password(PASSWORD, stored_hash)
    assert decode_access_token(token).sub == user.email
    assert data.user_id == str(user.user_id)


@pytest.mark.parametrize("found", [None, make_user()])
async def test_authenticate_rejects_unknown_email_or_wrong_password(monkeypatch, found):
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=found))

    with pytest.raises(UnauthorizedException) as exc:
        await auth_service.authenticate_user("tcg@tcgdigital.com", "WrongPass!")

    assert exc.value.detail == "Invalid email or password"


async def test_authenticate_marks_login_and_returns_token(monkeypatch):
    user = make_user(token_version=2)
    user.mark_login = AsyncMock()
    monkeypatch.setattr(User, "find_by_email", AsyncMock(return_value=user))

    token, data = await auth_service.authenticate_user("tcg@tcgdigital.com", PASSWORD)

    user.mark_login.assert_awaited_once()
    assert decode_access_token(token).ver == 2
    assert data.email == user.email


async def test_logout_revokes_the_token_until_it_expires(monkeypatch):
    user = make_user()
    add = AsyncMock()
    delete_expired = AsyncMock()
    monkeypatch.setattr(RevokedToken, "add", add)
    monkeypatch.setattr(RevokedToken, "delete_expired", delete_expired)
    payload = TokenPayload(sub=user.email, ver=0, jti="jti-1", exp=1792137600)

    await auth_service.logout_user(user, payload)

    jti, user_id, expires_at = add.await_args.args
    assert (jti, user_id) == ("jti-1", user.user_id)
    assert expires_at == datetime.fromtimestamp(1792137600, tz=timezone.utc)
    delete_expired.assert_awaited_once()


@pytest.mark.parametrize(
    "old, new, confirm, message",
    [
        (PASSWORD, "N3wStr0ngPass!", "Different1!", "do not match"),
        ("WrongPass!", "N3wStr0ngPass!", "N3wStr0ngPass!", "Current password is incorrect"),
        (PASSWORD, PASSWORD, PASSWORD, "must be different"),
    ],
)
async def test_change_password_rejects_bad_input(old, new, confirm, message):
    user = make_user()
    user.update_password = AsyncMock()
    data = ChangePasswordRequest(old_password=old, new_password=new, confirm_new_password=confirm)

    with pytest.raises(BadRequestException) as exc:
        await auth_service.change_password(user, data)

    assert message in exc.value.detail
    user.update_password.assert_not_awaited()


async def test_change_password_saves_new_hash_and_returns_fresh_token():
    user = make_user()

    async def fake_update(password_hash: str) -> None:
        user.password_hash = password_hash
        user.token_version += 1

    user.update_password = AsyncMock(side_effect=fake_update)
    data = ChangePasswordRequest(
        old_password=PASSWORD, new_password="N3wStr0ngPass!", confirm_new_password="N3wStr0ngPass!"
    )

    token = await auth_service.change_password(user, data)

    assert verify_password("N3wStr0ngPass!", user.password_hash)
    assert decode_access_token(token).ver == 1
