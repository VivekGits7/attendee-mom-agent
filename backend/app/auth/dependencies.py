from typing import Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.auth.model import RevokedToken, User
from app.auth.schemas import TokenPayload
from app.auth.utils import decode_access_token
from app.error import UnauthorizedException

SESSION_ENDED_MESSAGE = "Your session has ended. Please log in again."

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)


async def get_token_payload(token: Optional[str] = Depends(oauth2_scheme)) -> TokenPayload:
    if not token:
        raise UnauthorizedException("Please log in to continue")
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedException(SESSION_ENDED_MESSAGE)
    if await RevokedToken.is_revoked(payload.jti):
        raise UnauthorizedException(SESSION_ENDED_MESSAGE)
    return payload


async def get_current_user(payload: TokenPayload = Depends(get_token_payload)) -> User:
    user = await User.find_by_email(payload.sub)
    # A password change bumps token_version, which ends every older session.
    if user is None or user.token_version != payload.ver:
        raise UnauthorizedException(SESSION_ENDED_MESSAGE)
    return user
