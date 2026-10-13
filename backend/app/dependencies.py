import hmac
from typing import Optional

from fastapi import Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.error import UnauthorizedException

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> None:
    if (
        not api_key
        or not settings.INTERNAL_API_KEY
        or not hmac.compare_digest(api_key, settings.INTERNAL_API_KEY)
    ):
        raise UnauthorizedException("Invalid or missing API key")
