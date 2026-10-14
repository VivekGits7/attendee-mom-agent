from unittest.mock import AsyncMock
from datetime import datetime, timezone

from app.common import SortOrder
from app.meeting.enums import MeetingPlatform, MeetingSortBy, MeetingStatus
from app.meeting.model import Meeting


async def test_list_page_uses_bound_filters_and_counts_before_pagination(monkeypatch):
    from app.meeting import model

    count_query = AsyncMock(return_value={"total": 3})
    list_query = AsyncMock(return_value=[])
    monkeypatch.setattr(model, "execute_query_one", count_query)
    monkeypatch.setattr(model, "execute_query", list_query)

    meetings, total = await Meeting.list_page(
        "sprint' OR 1=1",
        MeetingStatus.JOINING,
        MeetingPlatform.GOOGLE_MEET,
        None,
        None,
        MeetingSortBy.TITLE,
        SortOrder.A_TO_Z,
        5,
        10,
    )

    assert meetings == []
    assert total == 3
    assert "sprint' OR 1=1" not in count_query.await_args.args[0]
    assert "title ILIKE $1" in count_query.await_args.args[0]
    assert "status = $2" in count_query.await_args.args[0]
    assert "platform = $3" in count_query.await_args.args[0]
    assert count_query.await_args.args[1:] == (
        "%sprint' OR 1=1%",
        "joining",
        "google_meet",
    )
    assert "ORDER BY LOWER(title) ASC NULLS LAST, meeting_id" in list_query.await_args.args[0]
    assert "LIMIT $4 OFFSET $5" in list_query.await_args.args[0]
    assert list_query.await_args.args[1:] == (
        "%sprint' OR 1=1%",
        "joining",
        "google_meet",
        5,
        10,
    )


async def test_update_progress_skips_older_state_change(monkeypatch):
    from datetime import datetime, timezone

    from app.meeting import model

    update = AsyncMock(return_value=None)
    monkeypatch.setattr(model, "execute_command_with_return", update)
    meeting = Meeting(meeting_id="m1", bot_state="ended")
    changed_at = datetime(2026, 10, 13, 10, 28, tzinfo=timezone.utc)

    applied = await meeting.update_progress("joined_recording", MeetingStatus.IN_PROGRESS, changed_at)

    assert applied is False
    assert meeting.bot_state == "ended"
    assert "bot_state_changed_at <= $7::timestamptz" in update.await_args.args[0]
    assert update.await_args.args[-1] == changed_at


async def test_schedule_page_filters_join_times_and_sorts_soonest_first(monkeypatch):
    from app.meeting import model

    count_query = AsyncMock(return_value={"total": 0})
    list_query = AsyncMock(return_value=[])
    monkeypatch.setattr(model, "execute_query_one", count_query)
    monkeypatch.setattr(model, "execute_query", list_query)
    start = datetime(2026, 10, 14, tzinfo=timezone.utc)
    end = datetime(2026, 11, 1, tzinfo=timezone.utc)

    await Meeting.list_page(
        None, MeetingStatus.SCHEDULED, None, start, end,
        MeetingSortBy.JOIN_AT, SortOrder.OLDEST, 100, 0,
    )

    assert "join_at >= $2" in count_query.await_args.args[0]
    assert "join_at < $3" in count_query.await_args.args[0]
    assert count_query.await_args.args[1:] == ("scheduled", start, end)
    assert "ORDER BY join_at ASC NULLS LAST, meeting_id" in list_query.await_args.args[0]
    assert "calendar_event_id, calendar_end_at" in list_query.await_args.args[0]


async def test_set_bot_keeps_state_written_by_an_earlier_webhook(monkeypatch):
    from app.meeting import model

    update = AsyncMock(return_value={"bot_state": "joining"})
    monkeypatch.setattr(model, "execute_command_with_return", update)
    meeting = Meeting(meeting_id="m1")

    await meeting.set_bot("bot_1", "ready")

    assert meeting.bot_state == "joining"
    assert "CASE WHEN bot_state_changed_at IS NULL THEN $3" in update.await_args.args[0]
