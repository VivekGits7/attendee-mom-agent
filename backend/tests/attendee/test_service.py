from datetime import datetime, timezone

import httpx
import pytest

from app.attendee import build_bot_payload, create_bot, get_transcript
from app.attendee import service as attendee_service
from app.config import settings
from app.error import ExternalServiceException


@pytest.fixture
def mock_attendee(monkeypatch):
    def install(handler):
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://attendee.test/api/v1",
        )
        monkeypatch.setattr(attendee_service, "_client", client)
        return client

    return install


def test_payload_has_auto_leave_webhooks_and_metadata(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIPTION_PROVIDER", "closed_captions")
    payload = build_bot_payload(
        "meeting-1", "https://meet.google.com/abc-defg-hij", None
    )

    leave = payload["automatic_leave_settings"]
    assert (
        leave["only_participant_in_meeting_timeout_seconds"]
        == settings.BOT_ONLY_PARTICIPANT_TIMEOUT_SECONDS
    )
    assert leave["max_uptime_seconds"] == settings.BOT_MAX_UPTIME_SECONDS
    assert "bot" in leave["bot_keywords"]
    assert payload["webhooks"][0]["url"] == settings.ATTENDEE_WEBHOOK_URL
    assert set(payload["webhooks"][0]["triggers"]) == {
        "transcript.update",
        "bot.state_change",
    }
    assert payload["metadata"] == {"meeting_id": "meeting-1"}
    assert payload["transcription_settings"] == {"meeting_closed_captions": {}}
    assert "join_at" not in payload


def test_payload_includes_join_at_and_deepgram(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIPTION_PROVIDER", "deepgram")
    join_at = datetime(2026, 10, 12, 10, 0, tzinfo=timezone.utc)

    payload = build_bot_payload(
        "meeting-1", "https://meet.google.com/abc-defg-hij", join_at
    )

    assert payload["join_at"] == "2026-10-12T10:00:00+00:00"
    assert payload["transcription_settings"] == {
        "deepgram": {
            "language": settings.DEEPGRAM_LANGUAGE,
            "model": settings.DEEPGRAM_MODEL,
        }
    }


def test_payload_requests_openai_transcription(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIPTION_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-transcribe")

    payload = build_bot_payload(
        "meeting-1", "https://meet.google.com/abc-defg-hij", None
    )

    assert payload["transcription_settings"] == {
        "openai": {"model": "gpt-4o-transcribe"}
    }


async def test_create_bot_sends_token_and_parses_bot(mock_attendee):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(
            201,
            json={
                "id": "bot_123",
                "state": "joining",
                "transcription_state": "not_started",
            },
        )

    mock_attendee(handler)
    bot = await create_bot({"meeting_url": "https://meet.google.com/abc-defg-hij"})

    assert seen["path"] == "/api/v1/bots"
    assert bot.id == "bot_123"
    assert bot.state == "joining"


async def test_attendee_error_becomes_502(mock_attendee):
    mock_attendee(
        lambda request: httpx.Response(400, json={"meeting_url": ["invalid"]})
    )

    with pytest.raises(ExternalServiceException):
        await create_bot({"meeting_url": "bad"})


async def test_get_transcript_reads_speaker_and_text(mock_attendee):
    utterances = [
        {
            "speaker_name": "Vivek Vishwakarma",
            "speaker_uuid": "16778240",
            "speaker_user_uuid": None,
            "speaker_is_host": True,
            "timestamp_ms": 1079,
            "duration_ms": 7710,
            "transcription": {"transcript": "Let's cook."},
        }
    ]
    mock_attendee(lambda request: httpx.Response(200, json=utterances))

    result = await get_transcript("bot_123")

    assert result[0].speaker_name == "Vivek Vishwakarma"
    assert result[0].text == "Let's cook."
