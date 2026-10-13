import base64

from app.attendee import sign_attendee_payload, verify_attendee_signature
from app.config import settings

PAYLOAD = {
    "idempotency_key": "6f1c2a9e-8f7b-4b8e-9d3c-2a1b0c9d8e7f",
    "bot_id": "bot_abc123",
    "bot_metadata": {"meeting_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"},
    "trigger": "transcript.update",
    "data": {
        "speaker_name": "Vivek",
        "transcription": {"transcript": "Namaste, ship it ✅"},
    },
}


def test_valid_signature_passes():
    signature = sign_attendee_payload(PAYLOAD, settings.ATTENDEE_WEBHOOK_SECRET)
    assert verify_attendee_signature(PAYLOAD, signature)


def test_key_order_does_not_change_signature():
    signature = sign_attendee_payload(PAYLOAD, settings.ATTENDEE_WEBHOOK_SECRET)
    reordered = dict(reversed(list(PAYLOAD.items())))
    assert verify_attendee_signature(reordered, signature)


def test_tampered_body_fails():
    signature = sign_attendee_payload(PAYLOAD, settings.ATTENDEE_WEBHOOK_SECRET)
    tampered = {**PAYLOAD, "data": {**PAYLOAD["data"], "speaker_name": "Someone else"}}
    assert not verify_attendee_signature(tampered, signature)


def test_wrong_secret_fails():
    other_secret = base64.b64encode(b"another-secret-entirely").decode()
    assert not verify_attendee_signature(
        PAYLOAD, sign_attendee_payload(PAYLOAD, other_secret)
    )


def test_missing_signature_fails():
    assert not verify_attendee_signature(PAYLOAD, None)
    assert not verify_attendee_signature(PAYLOAD, "")
