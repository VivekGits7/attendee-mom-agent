from datetime import datetime
from typing import List, Optional

import httpx

from app.attendee.enums import AttendeeTrigger, TranscriptionProvider
from app.attendee.schemas import AttendeeBot, AttendeeUtterance
from app.config import settings
from app.error import ExternalServiceException
from app.logger import get_logger

logger = get_logger(__name__)

_client: Optional[httpx.AsyncClient] = None


def get_attendee_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=f"{settings.ATTENDEE_BASE_URL.rstrip('/')}/api/v1",
            headers={
                "Authorization": f"Token {settings.ATTENDEE_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=settings.ATTENDEE_TIMEOUT_SECONDS,
        )
    return _client


async def close_attendee_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request(
    method: str, path: str, json: Optional[dict] = None
) -> httpx.Response:
    try:
        response = await get_attendee_client().request(method, path, json=json)
    except httpx.HTTPError as e:
        logger.error(f"Attendee {method} {path} failed: {type(e).__name__}")
        raise ExternalServiceException("Meeting bot service is unreachable") from e
    if response.status_code >= 400:
        logger.error(
            f"Attendee {method} {path} returned {response.status_code}: {response.text[:500]}"
        )
        raise ExternalServiceException("Meeting bot service rejected the request")
    return response


def _transcription_settings() -> dict:
    if settings.TRANSCRIPTION_PROVIDER == TranscriptionProvider.OPENAI.value:
        return {"openai": {"model": settings.OPENAI_TRANSCRIPTION_MODEL}}
    if settings.TRANSCRIPTION_PROVIDER == TranscriptionProvider.DEEPGRAM.value:
        return {
            "deepgram": {
                "language": settings.DEEPGRAM_LANGUAGE,
                "model": settings.DEEPGRAM_MODEL,
            }
        }
    return {"meeting_closed_captions": {}}


def build_bot_payload(
    meeting_id: str, meeting_url: str, join_at: Optional[datetime]
) -> dict:
    payload = {
        "meeting_url": meeting_url,
        "bot_name": settings.ATTENDEE_BOT_NAME,
        "metadata": {"meeting_id": meeting_id},
        "transcription_settings": _transcription_settings(),
        "automatic_leave_settings": {
            "only_participant_in_meeting_timeout_seconds": settings.BOT_ONLY_PARTICIPANT_TIMEOUT_SECONDS,
            "wait_for_host_to_start_meeting_timeout_seconds": settings.BOT_WAIT_FOR_HOST_TIMEOUT_SECONDS,
            "waiting_room_timeout_seconds": settings.BOT_WAITING_ROOM_TIMEOUT_SECONDS,
            "silence_timeout_seconds": settings.BOT_SILENCE_TIMEOUT_SECONDS,
            "silence_activate_after_seconds": settings.BOT_SILENCE_ACTIVATE_AFTER_SECONDS,
            "max_uptime_seconds": settings.BOT_MAX_UPTIME_SECONDS,
            "bot_keywords": settings.BOT_KEYWORDS,
        },
        "webhooks": [
            {
                "url": settings.ATTENDEE_WEBHOOK_URL,
                "triggers": [
                    AttendeeTrigger.TRANSCRIPT_UPDATE.value,
                    AttendeeTrigger.BOT_STATE_CHANGE.value,
                ],
            }
        ],
    }
    if join_at:
        payload["join_at"] = join_at.isoformat()
    return payload


async def create_bot(payload: dict) -> AttendeeBot:
    response = await _request("POST", "/bots", json=payload)
    return AttendeeBot.model_validate(response.json())


async def get_bot(bot_id: str) -> AttendeeBot:
    response = await _request("GET", f"/bots/{bot_id}")
    return AttendeeBot.model_validate(response.json())


async def get_transcript(bot_id: str) -> List[AttendeeUtterance]:
    response = await _request("GET", f"/bots/{bot_id}/transcript")
    return [AttendeeUtterance.model_validate(item) for item in response.json()]


async def leave_bot(bot_id: str) -> None:
    await _request("POST", f"/bots/{bot_id}/leave")
