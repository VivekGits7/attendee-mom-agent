from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx

from app.meeting import calendar
from app.meeting.enums import MeetingStatus
from app.microsoft import service as microsoft_service
from app.microsoft.service import CalendarEvent, parse_calendar_event


def event(start_offset_minutes=10):
    start = datetime.now(timezone.utc) + timedelta(minutes=start_offset_minutes)
    return CalendarEvent(
        event_id="graph-event-1",
        title="Sprint planning",
        meeting_url="https://teams.microsoft.com/l/meetup-join/abc?context=xyz",
        start_at=start,
        end_at=start + timedelta(minutes=30),
        organizer_email="vivek@tcg.com",
    )


def test_graph_event_uses_teams_url_from_body():
    meeting = event()
    raw = {
        "id": meeting.event_id,
        "subject": meeting.title,
        "start": {"dateTime": meeting.start_at.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": meeting.end_at.isoformat(), "timeZone": "UTC"},
        "body": {"content": '<a href="https://teams.microsoft.com/l/meetup-join/abc?x=1&amp;y=2">Join</a>'},
        "organizer": {"emailAddress": {"address": meeting.organizer_email}},
    }

    parsed = parse_calendar_event(raw)

    assert parsed.event_id == meeting.event_id
    assert parsed.meeting_url.endswith("?x=1&y=2")
    assert parsed.organizer_email == meeting.organizer_email


async def test_graph_calendar_reads_every_page(monkeypatch):
    meeting = event()
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "test-token"})
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json={"value": []})
        return httpx.Response(200, json={
            "value": [{
                "id": meeting.event_id,
                "subject": meeting.title,
                "start": {"dateTime": meeting.start_at.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": meeting.end_at.isoformat(), "timeZone": "UTC"},
                "onlineMeeting": {"joinUrl": meeting.meeting_url},
            }],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/users/MOM%40tcgdigital.com/calendar/calendarView?page=2",
        })

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        microsoft_service.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(microsoft_service.settings, "MICROSOFT_TENANT_ID", "test-tenant")
    monkeypatch.setattr(microsoft_service.settings, "MICROSOFT_CLIENT_ID", "test-client")
    monkeypatch.setattr(microsoft_service.settings, "MICROSOFT_CLIENT_SECRET", "test-secret")

    events, ids, _, _ = await microsoft_service.list_calendar_events()

    assert len(events) == 1
    assert ids == {meeting.event_id}
    assert len(requests) == 3
    assert requests[1].headers["Authorization"] == "Bearer test-token"


async def test_new_calendar_event_creates_one_scheduled_bot(monkeypatch):
    meeting = SimpleNamespace(
        meeting_id="meeting-1", bot_id=None, set_bot=AsyncMock(),
        mark_status=AsyncMock(), update_calendar_details=AsyncMock(),
    )
    find = AsyncMock(return_value=None)
    insert = AsyncMock(return_value=meeting)
    create = AsyncMock(return_value=SimpleNamespace(id="bot-1", state="scheduled"))
    monkeypatch.setattr(calendar.Meeting, "find_by_calendar_event_id", find)
    monkeypatch.setattr(calendar.Meeting, "create_from_calendar", insert)
    monkeypatch.setattr(calendar, "create_bot", create)

    await calendar._schedule_event(event())

    insert.assert_awaited_once()
    assert insert.await_args.args[3] == "vivek@tcg.com"
    assert create.await_args.args[0]["join_at"]
    meeting.set_bot.assert_awaited_once_with("bot-1", "scheduled")


async def test_existing_event_does_not_reschedule_at_start(monkeypatch):
    current = event(start_offset_minutes=-1)
    meeting = SimpleNamespace(
        status=MeetingStatus.SCHEDULED.value,
        bot_id="bot-1",
        title=current.title,
        meeting_url=current.meeting_url,
        join_at=current.start_at,
        calendar_end_at=current.end_at,
    )
    monkeypatch.setattr(calendar.Meeting, "find_by_calendar_event_id", AsyncMock(return_value=meeting))
    update = AsyncMock()
    delete = AsyncMock()
    monkeypatch.setattr(calendar, "update_scheduled_bot", update)
    monkeypatch.setattr(calendar, "delete_scheduled_bot", delete)

    await calendar._schedule_event(current)

    update.assert_not_awaited()
    delete.assert_not_awaited()


async def test_cancelled_event_removes_scheduled_bot(monkeypatch):
    meeting = SimpleNamespace(
        bot_id="bot-1", calendar_event_id="cancelled-event", clear_calendar_bot=AsyncMock()
    )
    monkeypatch.setattr(calendar, "list_calendar_events", AsyncMock(return_value=(
        [], set(), datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=1)
    )))
    monkeypatch.setattr(calendar.Meeting, "list_scheduled_calendar_meetings", AsyncMock(return_value=[meeting]))
    remove = AsyncMock()
    monkeypatch.setattr(calendar, "delete_scheduled_bot", remove)

    await calendar.sync_teams_calendar()

    remove.assert_awaited_once_with("bot-1")
    meeting.clear_calendar_bot.assert_awaited_once_with("Teams calendar invitation was cancelled or removed")
