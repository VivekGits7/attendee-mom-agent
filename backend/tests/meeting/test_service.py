import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.attendee import AttendeeBot, AttendeeTrigger, AttendeeUtterance, AttendeeWebhookEnvelope
from app.error import ConflictException, ExternalServiceException
from app.meeting import service as meeting_service
from app.meeting.enums import EmailStatus, MeetingStatus, NoTranscriptReason
from app.meeting.model import Meeting
from app.mom import MeetingMinutes, Outcome

MINUTES = MeetingMinutes(
    summary="Sprint scope agreed.",
    outcomes=[Outcome(item="Share API contract", owner="Vivek", due_date="Friday")],
    open_questions=[],
)


def make_meeting(**overrides) -> Meeting:
    fields = {
        "meeting_id": uuid.uuid4(),
        "title": "Sprint planning",
        "meeting_url": "https://meet.google.com/abc-defg-hij",
        "platform": "google_meet",
        "bot_id": "bot_1",
        "bot_state": "joined_recording",
        "status": MeetingStatus.IN_PROGRESS.value,
        "recipient_email": "vivek@tcg.com",
        "email_status": EmailStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc),
    }
    fields.update(overrides)
    meeting = Meeting(**fields)
    for method in (
        "set_bot",
        "update_progress",
        "mark_status",
        "save_minutes",
        "set_email_result",
    ):
        setattr(meeting, method, AsyncMock())
    meeting.update_progress = AsyncMock(return_value=True)
    return meeting


def envelope(trigger: str, data: dict, meeting: Meeting) -> AttendeeWebhookEnvelope:
    return AttendeeWebhookEnvelope(
        idempotency_key=uuid.uuid4(),
        bot_id=meeting.bot_id,
        bot_metadata={"meeting_id": str(meeting.meeting_id)},
        trigger=trigger,
        data=data,
    )


UTTERANCE_DATA = {
    "speaker_name": "Vivek",
    "speaker_uuid": "1",
    "speaker_is_host": True,
    "timestamp_ms": 1000,
    "duration_ms": 2000,
    "transcription": {"transcript": "Let's cook."},
}


async def test_old_bot_webhook_is_ignored_after_calendar_reschedule(monkeypatch):
    meeting = make_meeting(bot_id="bot-new", calendar_event_id="calendar-event")
    old_event = envelope(AttendeeTrigger.BOT_STATE_CHANGE.value, {}, meeting)
    old_event.bot_id = "bot-old"
    monkeypatch.setattr(
        meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
    )

    result = await meeting_service._find_meeting_for_webhook(old_event)

    assert result is None


class TestDeliverMinutes:
    async def test_sends_to_allowed_recipient(self, monkeypatch):
        send = AsyncMock()
        monkeypatch.setattr(meeting_service, "send_email", send)
        meeting = make_meeting()

        await meeting_service._deliver_minutes(meeting, MINUTES)

        assert send.await_args.args[0] == "vivek@tcg.com"
        meeting.set_email_result.assert_awaited_once_with(
            EmailStatus.SENT, "vivek@tcg.com"
        )

    @pytest.mark.parametrize("recipient", ["vivek@gmail.com", None])
    async def test_off_domain_or_missing_goes_to_default(self, monkeypatch, recipient):
        send = AsyncMock()
        monkeypatch.setattr(meeting_service, "send_email", send)
        meeting = make_meeting(recipient_email=recipient)

        await meeting_service._deliver_minutes(meeting, MINUTES)

        assert send.await_args.args[0] == "meetings@tcg.com"
        meeting.set_email_result.assert_awaited_once_with(
            EmailStatus.SENT_TO_FALLBACK, "meetings@tcg.com"
        )

    async def test_primary_failure_falls_back_to_default(self, monkeypatch):
        send = AsyncMock(side_effect=[ExternalServiceException(), None])
        monkeypatch.setattr(meeting_service, "send_email", send)
        meeting = make_meeting()

        await meeting_service._deliver_minutes(meeting, MINUTES)

        assert [call.args[0] for call in send.await_args_list] == [
            "vivek@tcg.com",
            "meetings@tcg.com",
        ]
        meeting.set_email_result.assert_awaited_once_with(
            EmailStatus.SENT_TO_FALLBACK, "meetings@tcg.com"
        )

    async def test_both_failures_mark_email_failed(self, monkeypatch):
        monkeypatch.setattr(
            meeting_service,
            "send_email",
            AsyncMock(side_effect=ExternalServiceException()),
        )
        meeting = make_meeting()

        await meeting_service._deliver_minutes(meeting, MINUTES)

        meeting.set_email_result.assert_awaited_once_with(EmailStatus.FAILED, None)


class TestStateChange:
    async def test_ended_claims_and_schedules_finalize(self, monkeypatch):
        claim = AsyncMock(return_value=True)
        monkeypatch.setattr(meeting_service.Meeting, "claim_for_processing", claim)
        tasks = BackgroundTasks()
        meeting = make_meeting()

        await meeting_service._apply_state_change(
            meeting, {"old_state": "post_processing", "new_state": "ended"}, tasks
        )

        claim.assert_awaited_once_with(meeting.meeting_id)
        assert len(tasks.tasks) == 1
        assert tasks.tasks[0].func is meeting_service.finalize_meeting

    async def test_second_ended_event_does_not_schedule_again(self, monkeypatch):
        monkeypatch.setattr(
            meeting_service.Meeting,
            "claim_for_processing",
            AsyncMock(return_value=False),
        )
        tasks = BackgroundTasks()

        await meeting_service._apply_state_change(
            make_meeting(), {"new_state": "ended"}, tasks
        )

        assert tasks.tasks == []

    async def test_joined_updates_progress_only(self, monkeypatch):
        claim = AsyncMock()
        monkeypatch.setattr(meeting_service.Meeting, "claim_for_processing", claim)
        tasks = BackgroundTasks()
        meeting = make_meeting(status=MeetingStatus.JOINING.value)

        await meeting_service._apply_state_change(
            meeting, {"old_state": "joining", "new_state": "joined_recording"}, tasks
        )

        meeting.update_progress.assert_awaited_once_with(
            "joined_recording", MeetingStatus.IN_PROGRESS, None
        )
        claim.assert_not_awaited()
        assert tasks.tasks == []

    async def test_event_time_is_passed_to_progress(self, monkeypatch):
        monkeypatch.setattr(meeting_service.Meeting, "claim_for_processing", AsyncMock())
        meeting = make_meeting()

        await meeting_service._apply_state_change(
            meeting,
            {"new_state": "joined_recording", "created_at": "2026-10-13T10:28:30.572634+00:00"},
            BackgroundTasks(),
        )

        assert meeting.update_progress.await_args.args[2] == datetime(
            2026, 10, 13, 10, 28, 30, 572634, tzinfo=timezone.utc
        )

    async def test_stale_ended_event_does_not_finalize(self, monkeypatch):
        claim = AsyncMock(return_value=True)
        monkeypatch.setattr(meeting_service.Meeting, "claim_for_processing", claim)
        tasks = BackgroundTasks()
        meeting = make_meeting()
        meeting.update_progress = AsyncMock(return_value=False)

        await meeting_service._apply_state_change(
            meeting,
            {"new_state": "ended", "created_at": "2026-10-13T10:00:00+00:00"},
            tasks,
        )

        claim.assert_not_awaited()
        assert tasks.tasks == []


class TestLeave:
    @pytest.mark.parametrize("bot_state", ["leaving", "post_processing", "ended", "fatal_error"])
    async def test_rejects_bot_that_already_left(self, monkeypatch, bot_state):
        monkeypatch.setattr(
            meeting_service.Meeting,
            "find_by_id",
            AsyncMock(return_value=make_meeting(bot_state=bot_state)),
        )
        leave = AsyncMock()
        monkeypatch.setattr(meeting_service, "leave_bot", leave)

        with pytest.raises(ConflictException):
            await meeting_service.request_bot_leave(str(uuid.uuid4()))

        leave.assert_not_awaited()


class TestWebhookHandler:
    async def test_duplicate_delivery_is_ignored(self, monkeypatch):
        monkeypatch.setattr(
            meeting_service.AttendeeWebhookEvent,
            "record",
            AsyncMock(return_value=False),
        )
        find = AsyncMock()
        monkeypatch.setattr(meeting_service.Meeting, "find_by_id", find)

        await meeting_service.handle_attendee_webhook(
            envelope("transcript.update", UTTERANCE_DATA, make_meeting()),
            BackgroundTasks(),
        )

        find.assert_not_awaited()

    async def test_transcript_update_stores_utterance(self, monkeypatch):
        meeting = make_meeting()
        monkeypatch.setattr(
            meeting_service.AttendeeWebhookEvent, "record", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
        )
        upsert = AsyncMock()
        monkeypatch.setattr(meeting_service.MeetingUtterance, "upsert", upsert)

        await meeting_service.handle_attendee_webhook(
            envelope("transcript.update", UTTERANCE_DATA, meeting), BackgroundTasks()
        )

        stored: AttendeeUtterance = upsert.await_args.args[1]
        assert stored.speaker_name == "Vivek"
        assert stored.text == "Let's cook."

    async def test_live_lines_after_meeting_closed_are_skipped(self, monkeypatch):
        meeting = make_meeting(status=MeetingStatus.PROCESSING.value)
        monkeypatch.setattr(
            meeting_service.AttendeeWebhookEvent, "record", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(
            meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
        )
        upsert = AsyncMock()
        monkeypatch.setattr(meeting_service.MeetingUtterance, "upsert", upsert)

        await meeting_service.handle_attendee_webhook(
            envelope("transcript.update", UTTERANCE_DATA, meeting), BackgroundTasks()
        )

        upsert.assert_not_awaited()

    async def test_failure_forgets_delivery_so_retry_works(self, monkeypatch):
        meeting = make_meeting()
        monkeypatch.setattr(
            meeting_service.AttendeeWebhookEvent, "record", AsyncMock(return_value=True)
        )
        forget = AsyncMock()
        monkeypatch.setattr(meeting_service.AttendeeWebhookEvent, "forget", forget)
        monkeypatch.setattr(
            meeting_service.Meeting,
            "find_by_id",
            AsyncMock(side_effect=RuntimeError("db down")),
        )
        event = envelope("transcript.update", UTTERANCE_DATA, meeting)

        with pytest.raises(RuntimeError):
            await meeting_service.handle_attendee_webhook(event, BackgroundTasks())

        forget.assert_awaited_once_with(event.idempotency_key)


class TestFinalize:
    @pytest.mark.parametrize(
        ("transcription_state", "joined", "reason"),
        [
            ("complete", True, NoTranscriptReason.NO_WORDS),
            ("complete", False, NoTranscriptReason.NOBODY_JOINED),
            ("failed", True, NoTranscriptReason.TRANSCRIPTION_FAILED),
        ],
    )
    async def test_empty_transcript_marks_failed_with_reason(
        self, monkeypatch, transcription_state, joined, reason
    ):
        meeting = make_meeting()
        monkeypatch.setattr(
            meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
        )
        monkeypatch.setattr(meeting_service, "_sync_final_transcript", AsyncMock())
        monkeypatch.setattr(
            meeting_service.MeetingUtterance,
            "list_by_meeting",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            meeting_service,
            "get_bot",
            AsyncMock(
                return_value=AttendeeBot(id="bot_1", transcription_state=transcription_state)
            ),
        )
        monkeypatch.setattr(
            meeting_service, "has_participants", AsyncMock(return_value=joined)
        )
        generate = AsyncMock()
        monkeypatch.setattr(meeting_service, "generate_minutes", generate)

        await meeting_service.finalize_meeting(str(meeting.meeting_id))

        meeting.mark_status.assert_awaited_once_with(MeetingStatus.FAILED, reason.value)
        generate.assert_not_awaited()

    async def test_empty_transcript_when_attendee_is_down(self, monkeypatch):
        monkeypatch.setattr(
            meeting_service,
            "get_bot",
            AsyncMock(side_effect=ExternalServiceException()),
        )

        reason = await meeting_service._no_transcript_reason(make_meeting())

        assert reason is NoTranscriptReason.UNKNOWN

    async def test_happy_path_saves_minutes_and_emails(self, monkeypatch):
        meeting = make_meeting()
        lines = [
            SimpleNamespace(
                speaker_name="Vivek", timestamp_ms=0, text="Ship it Friday."
            )
        ]
        monkeypatch.setattr(
            meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
        )
        monkeypatch.setattr(meeting_service, "_sync_final_transcript", AsyncMock())
        monkeypatch.setattr(
            meeting_service.MeetingUtterance,
            "list_by_meeting",
            AsyncMock(return_value=lines),
        )
        generate = AsyncMock(return_value=MINUTES)
        monkeypatch.setattr(meeting_service, "generate_minutes", generate)
        deliver = AsyncMock()
        monkeypatch.setattr(meeting_service, "_deliver_minutes", deliver)

        await meeting_service.finalize_meeting(str(meeting.meeting_id))

        assert generate.await_args.args == (
            "[00:00:00] Vivek: Ship it Friday.",
        )
        meeting.save_minutes.assert_awaited_once_with(MINUTES.model_dump(mode="json"))
        meeting.mark_status.assert_awaited_once_with(MeetingStatus.COMPLETED)
        deliver.assert_awaited_once_with(meeting, MINUTES)

    async def test_openai_failure_marks_failed(self, monkeypatch):
        meeting = make_meeting()
        lines = [SimpleNamespace(speaker_name="Vivek", timestamp_ms=0, text="Hello")]
        monkeypatch.setattr(
            meeting_service.Meeting, "find_by_id", AsyncMock(return_value=meeting)
        )
        monkeypatch.setattr(meeting_service, "_sync_final_transcript", AsyncMock())
        monkeypatch.setattr(
            meeting_service.MeetingUtterance,
            "list_by_meeting",
            AsyncMock(return_value=lines),
        )
        monkeypatch.setattr(
            meeting_service,
            "generate_minutes",
            AsyncMock(side_effect=ExternalServiceException()),
        )

        await meeting_service.finalize_meeting(str(meeting.meeting_id))

        assert meeting.mark_status.await_args.args[0] == MeetingStatus.FAILED

    async def test_final_transcript_replaces_live_lines_without_empty_text(
        self, monkeypatch
    ):
        meeting = make_meeting()
        final = [
            AttendeeUtterance(**UTTERANCE_DATA),
            AttendeeUtterance(
                **{
                    **UTTERANCE_DATA,
                    "timestamp_ms": 5000,
                    "transcription": {"transcript": "  "},
                }
            ),
        ]
        monkeypatch.setattr(
            meeting_service,
            "get_bot",
            AsyncMock(
                return_value=AttendeeBot(id="bot_1", transcription_state="complete")
            ),
        )
        monkeypatch.setattr(
            meeting_service, "get_transcript", AsyncMock(return_value=final)
        )
        replace = AsyncMock()
        monkeypatch.setattr(meeting_service.MeetingUtterance, "replace_all", replace)

        await meeting_service._sync_final_transcript(meeting)

        assert [u.timestamp_ms for u in replace.await_args.args[1]] == [1000]

    async def test_final_transcript_failure_keeps_live_lines(self, monkeypatch):
        monkeypatch.setattr(
            meeting_service,
            "get_bot",
            AsyncMock(side_effect=ExternalServiceException()),
        )
        replace = AsyncMock()
        monkeypatch.setattr(meeting_service.MeetingUtterance, "replace_all", replace)

        await meeting_service._sync_final_transcript(make_meeting())

        replace.assert_not_awaited()
