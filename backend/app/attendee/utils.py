import base64
import hashlib
import hmac
import json
from typing import Optional

from app.config import settings


def sign_attendee_payload(payload: dict, secret_b64: str) -> str:
    secret = base64.b64decode(secret_b64)
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return base64.b64encode(
        hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")


def verify_attendee_signature(payload: dict, signature: Optional[str]) -> bool:
    if not signature or not settings.ATTENDEE_WEBHOOK_SECRET:
        return False
    expected = sign_attendee_payload(payload, settings.ATTENDEE_WEBHOOK_SECRET)
    return hmac.compare_digest(signature, expected)
