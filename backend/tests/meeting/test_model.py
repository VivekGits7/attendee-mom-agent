from unittest.mock import AsyncMock

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
