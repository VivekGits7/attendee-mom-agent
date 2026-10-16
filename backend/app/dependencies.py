import hmac
from typing import Optional

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader

from app.auth.dependencies import get_current_user, get_token_payload, oauth2_scheme
from app.auth.model import User
from app.config import settings
from app.error import UnauthorizedException

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _is_valid_api_key(api_key: Optional[str]) -> bool:
    if not api_key or not settings.INTERNAL_API_KEY:
        return False
    return hmac.compare_digest(api_key.encode(), settings.INTERNAL_API_KEY.encode())


async def require_user_or_api_key(
    api_key: Optional[str] = Security(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme),
) -> None:
    if _is_valid_api_key(api_key):
        return
    if token:
        await get_current_user(await get_token_payload(token))
        return
    raise UnauthorizedException("Invalid or missing API key" if api_key else "Please log in to continue")


async def authenticate_ws(token: object) -> Optional[User]:
    if not isinstance(token, str) or not token:
        return None
    try:
        return await get_current_user(await get_token_payload(token))
    except UnauthorizedException:
        return None
