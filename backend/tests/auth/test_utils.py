from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth.utils import create_access_token, decode_access_token, hash_password, verify_password
from app.config import settings

EMAIL = "tcg@tcgdigital.com"


def _future() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=5)


def test_hash_and_verify_password():
    hashed = hash_password("Str0ngPass!")

    assert hashed != "Str0ngPass!"
    assert verify_password("Str0ngPass!", hashed)
    assert not verify_password("WrongPass!", hashed)


def test_password_longer_than_bcrypt_limit_still_verifies():
    password = "é" * 50
    assert verify_password(password, hash_password(password))


def test_access_token_round_trip():
    payload = decode_access_token(create_access_token(EMAIL, 3))

    assert payload.sub == EMAIL
    assert payload.ver == 3
    assert payload.exp > datetime.now(timezone.utc).timestamp()


def test_every_token_gets_a_unique_jti():
    first = decode_access_token(create_access_token(EMAIL, 0))
    second = decode_access_token(create_access_token(EMAIL, 0))
    assert first.jti != second.jti


def test_token_signed_with_another_secret_is_rejected():
    claims = {"sub": EMAIL, "ver": 0, "jti": "abc", "exp": _future()}
    token = jwt.encode(claims, "some-other-secret", algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_expired_token_is_rejected():
    claims = {"sub": EMAIL, "ver": 0, "jti": "abc", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}
    token = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_token_without_required_claims_is_rejected():
    token = jwt.encode({"sub": EMAIL, "exp": _future()}, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    assert decode_access_token(token) is None


def test_garbage_token_is_rejected():
    assert decode_access_token("not-a-jwt") is None
