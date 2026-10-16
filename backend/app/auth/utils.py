import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import ValidationError

from app.auth.schemas import TokenPayload
from app.config import settings

BCRYPT_MAX_BYTES = 72

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _bcrypt_secret(password: str) -> bytes:
    return password.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return pwd_context.hash(_bcrypt_secret(password))


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(_bcrypt_secret(password), password_hash)


def access_token_expires_in() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def create_access_token(email: str, token_version: int) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": email,
        "ver": token_version,
        "jti": secrets.token_urlsafe(32),
        "iat": now,
        "exp": now + timedelta(seconds=access_token_expires_in()),
    }
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[TokenPayload]:
    try:
        claims = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenPayload.model_validate(claims)
    except (JWTError, ValidationError):
        return None
