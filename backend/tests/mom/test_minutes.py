from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.mom import MeetingMinutes, Outcome
from app.mom import service as mom_service
from app.prompts import get_system_prompt


def test_older_saved_minutes_can_still_be_read():
    old = {
        "summary": "The release moved.",
        "decisions": [{"decision": "Move the release", "made_by": "Group"}],
        "action_items": [
            {"task": "Update the plan", "owner": "Vivek", "due_date": "Friday"}
        ],
        "open_questions": ["Who will approve it?"],
    }

    minutes = MeetingMinutes.model_validate(old)

    assert minutes.outcomes == [
        Outcome(item="Move the release", owner=None, due_date=None),
        Outcome(item="Update the plan", owner="Vivek", due_date="Friday"),
    ]
    assert minutes.open_questions == ["Who will approve it?"]


@pytest.mark.asyncio
async def test_generation_uses_reference_prompt_and_three_field_schema(monkeypatch):
    minutes = MeetingMinutes(summary="We agreed to ship.", outcomes=[], open_questions=[])
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=minutes))
    monkeypatch.setattr(
        mom_service,
        "get_openai_client",
        lambda: SimpleNamespace(responses=SimpleNamespace(parse=parse)),
    )

    result = await mom_service.generate_minutes("Vivek: Ship the release on Friday.")

    assert result is minutes
    assert parse.await_args.kwargs["input"] == "Vivek: Ship the release on Friday."
    assert parse.await_args.kwargs["instructions"] == get_system_prompt("mom")
    assert parse.await_args.kwargs["text_format"] is MeetingMinutes
    assert set(MeetingMinutes.model_fields) == {"summary", "outcomes", "open_questions"}
