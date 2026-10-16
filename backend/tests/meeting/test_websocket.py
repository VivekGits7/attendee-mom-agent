import asyncio
import time
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.error import NotFoundException
from app.main import app
from app.meeting import router as meeting_router_module
from app.meeting.schemas import MEETING_EXAMPLE, LiveTranscriptData, MeetingData, UtteranceData
from app.meeting.utils import RESYNC, live_transcript_hub

MEETING_ID = MEETING_EXAMPLE["meeting_id"]
PATH = f"/api/ws/meetings/{MEETING_ID}/transcript"


def line(text: str, timestamp_ms: int = 1000) -> UtteranceData:
    return UtteranceData(
        utterance_id=str(uuid.uuid4()),
        speaker_name="TCG User",
        speaker_is_host=True,
        timestamp_ms=timestamp_ms,
        duration_ms=500,
        text=text,
    )


def snapshot(*texts: str) -> LiveTranscriptData:
    return LiveTranscriptData(
        meeting=MeetingData(**MEETING_EXAMPLE),
        utterances=[line(text, 1000 + index) for index, text in enumerate(texts)],
    )


def wait_until(condition, seconds: float = 2.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


def closed_with(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as closed:
        ws.receive_json()
    return closed.value.code


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(meeting_router_module, "authenticate_ws", AsyncMock(return_value=object()))
    monkeypatch.setattr(meeting_router_module, "get_live_snapshot", AsyncMock(return_value=snapshot("Hello")))
    return TestClient(app)


def test_bad_token_closes_with_4001(client, monkeypatch):
    monkeypatch.setattr(meeting_router_module, "authenticate_ws", AsyncMock(return_value=None))
    with client.websocket_connect(PATH) as ws:
        ws.send_json({"token": "nope"})
        assert ws.receive_json() == {"type": "failed", "message": "Please log in to continue"}
        assert closed_with(ws) == 4001


def test_no_token_in_time_closes_with_4001(monkeypatch):
    monkeypatch.setattr(settings, "LIVE_TRANSCRIPT_AUTH_TIMEOUT_SECONDS", 0.05)
    with TestClient(app).websocket_connect(PATH) as ws:
        assert ws.receive_json()["type"] == "failed"
        assert closed_with(ws) == 4001


def test_bad_meeting_id_closes_with_4002(client):
    with client.websocket_connect("/api/ws/meetings/not-a-uuid/transcript") as ws:
        ws.send_json({"token": "t"})
        assert ws.receive_json()["type"] == "failed"
        assert closed_with(ws) == 4002


def test_unknown_meeting_closes_with_4004(client, monkeypatch):
    monkeypatch.setattr(
        meeting_router_module, "get_live_snapshot", AsyncMock(side_effect=NotFoundException("Meeting not found"))
    )
    with client.websocket_connect(PATH) as ws:
        ws.send_json({"token": "t"})
        assert ws.receive_json() == {"type": "failed", "message": "Meeting not found"}
        assert closed_with(ws) == 4004


def test_snapshot_then_live_lines_then_resync(client, monkeypatch):
    with client.websocket_connect(PATH) as ws:
        ws.send_json({"token": "t"})
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        assert [u["text"] for u in first["data"]["utterances"]] == ["Hello"]

        new_line = line("Let's cook.", 2000).model_dump()
        live_transcript_hub.publish(MEETING_ID, {"type": "utterance", "data": new_line})
        assert ws.receive_json() == {"type": "utterance", "data": new_line}

        monkeypatch.setattr(
            meeting_router_module, "get_live_snapshot", AsyncMock(return_value=snapshot("Hello", "Final line"))
        )
        live_transcript_hub.resync(MEETING_ID)
        resynced = ws.receive_json()
        assert resynced["type"] == "snapshot"
        assert [u["text"] for u in resynced["data"]["utterances"]] == ["Hello", "Final line"]

        ws.close()
        assert wait_until(lambda: not live_transcript_hub.has_subscribers(MEETING_ID))


def test_ping_rechecks_login_and_closes_when_it_ends(client, monkeypatch):
    monkeypatch.setattr(settings, "LIVE_TRANSCRIPT_PING_SECONDS", 0.05)
    monkeypatch.setattr(
        meeting_router_module, "authenticate_ws", AsyncMock(side_effect=[object(), object(), None])
    )
    with client.websocket_connect(PATH) as ws:
        ws.send_json({"token": "t"})
        assert ws.receive_json()["type"] == "snapshot"
        assert ws.receive_json() == {"type": "ping"}
        assert ws.receive_json() == {
            "type": "failed",
            "message": "Your session has ended. Please log in again.",
        }
        assert closed_with(ws) == 4001


async def test_slow_socket_drops_backlog_and_resyncs(monkeypatch):
    monkeypatch.setattr(settings, "LIVE_TRANSCRIPT_QUEUE_SIZE", 2)
    meeting_id = str(uuid.uuid4())
    queue = live_transcript_hub.subscribe(meeting_id)
    try:
        for index in range(4):
            live_transcript_hub.publish(meeting_id, {"index": index})
        await asyncio.sleep(0)
        assert queue.get_nowait() is RESYNC
        assert queue.get_nowait() == {"index": 3}
        assert queue.empty()
    finally:
        live_transcript_hub.unsubscribe(meeting_id, queue)
    assert not live_transcript_hub.has_subscribers(meeting_id)
