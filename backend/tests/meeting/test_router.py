import json
import uuid
from unittest.mock import AsyncMock

from app.attendee import sign_attendee_payload
from app.config import settings
from app.meeting import router as meeting_router_module
from app.meeting.schemas import MEETING_EXAMPLE, MeetingData

VALID_BODY = {
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "title": "Sprint planning",
    "recipient_email": "vivek@tcg.com",
}


def signed_webhook(body: dict) -> tuple[str, dict]:
    signature = sign_attendee_payload(body, settings.ATTENDEE_WEBHOOK_SECRET)
    return json.dumps(body), {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
    }


def webhook_body() -> dict:
    return {
        "idempotency_key": str(uuid.uuid4()),
        "bot_id": "bot_1",
        "bot_metadata": {"meeting_id": MEETING_EXAMPLE["meeting_id"]},
        "trigger": "bot.state_change",
        "data": {"old_state": "joining", "new_state": "joined_recording"},
    }


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["data"]["service"] == settings.APP_NAME


async def test_create_meeting_requires_api_key(client):
    response = await client.post("/api/meetings", json=VALID_BODY)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_create_meeting_rejects_zoom_link(client, api_headers):
    response = await client.post(
        "/api/meetings",
        json={**VALID_BODY, "meeting_url": "https://us05web.zoom.us/j/123"},
        headers=api_headers,
    )
    assert response.status_code == 422


async def test_create_meeting_rejects_past_join_at(client, api_headers):
    response = await client.post(
        "/api/meetings",
        json={**VALID_BODY, "join_at": "2020-01-01T10:00:00Z"},
        headers=api_headers,
    )
    assert response.status_code == 422


async def test_create_meeting_returns_201(client, api_headers, monkeypatch):
    monkeypatch.setattr(
        meeting_router_module,
        "create_meeting",
        AsyncMock(return_value=MeetingData(**MEETING_EXAMPLE)),
    )

    response = await client.post("/api/meetings", json=VALID_BODY, headers=api_headers)

    assert response.status_code == 201
    assert response.json()["data"]["bot_id"] == MEETING_EXAMPLE["bot_id"]


async def test_list_meetings_requires_api_key(client):
    response = await client.get("/api/meetings")
    assert response.status_code == 401


async def test_list_meetings_passes_filters_and_pagination(client, api_headers, monkeypatch):
    list_service = AsyncMock(return_value=([MeetingData(**MEETING_EXAMPLE)], 7))
    monkeypatch.setattr(meeting_router_module, "list_meetings", list_service)

    response = await client.get(
        "/api/meetings",
        params={
            "search": "sprint",
            "status": "joining",
            "platform": "google_meet",
            "sort_by": "title",
            "sort_order": "a_to_z",
            "limit": 5,
            "offset": 2,
        },
        headers=api_headers,
    )

    assert response.status_code == 200
    assert response.json()["total"] == 7
    assert len(response.json()["data"]) == 1
    assert list_service.await_args.args[0] == "sprint"
    assert list_service.await_args.args[1].value == "joining"
    assert list_service.await_args.args[2].value == "google_meet"
    assert list_service.await_args.args[4].value == "a_to_z"
    assert list_service.await_args.args[5:] == (5, 2)


async def test_list_meetings_rejects_invalid_sort(client, api_headers):
    response = await client.get(
        "/api/meetings", params={"sort_order": "DESC"}, headers=api_headers
    )
    assert response.status_code == 422


async def test_get_meeting_rejects_bad_uuid(client, api_headers):
    response = await client.get("/api/meetings/not-a-uuid", headers=api_headers)
    assert response.status_code == 400


async def test_webhook_rejects_missing_signature(client):
    response = await client.post("/api/webhooks/attendee", json=webhook_body())
    assert response.status_code == 401


async def test_webhook_rejects_invalid_json(client):
    response = await client.post(
        "/api/webhooks/attendee",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


async def test_webhook_rejects_signed_body_with_missing_fields(client):
    content, headers = signed_webhook({"trigger": "bot.state_change"})
    response = await client.post(
        "/api/webhooks/attendee", content=content, headers=headers
    )
    assert response.status_code == 400


async def test_webhook_accepts_signed_delivery(client, monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(meeting_router_module, "handle_attendee_webhook", handler)
    body = webhook_body()
    content, headers = signed_webhook(body)

    response = await client.post(
        "/api/webhooks/attendee", content=content, headers=headers
    )

    assert response.status_code == 200
    envelope = handler.await_args.args[0]
    assert str(envelope.idempotency_key) == body["idempotency_key"]
    assert envelope.data["new_state"] == "joined_recording"
