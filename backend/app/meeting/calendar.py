import asyncio
from datetime import datetime, timezone

from app.attendee import build_bot_payload, create_bot, delete_scheduled_bot, update_scheduled_bot
from app.config import settings
from app.error import ExternalServiceException
from app.logger import get_logger
from app.mail import is_allowed_recipient
from app.meeting.enums import MeetingStatus
from app.meeting.model import Meeting
from app.microsoft import CalendarEvent, list_calendar_events

logger = get_logger(__name__)


async def _schedule_event(event: CalendarEvent) -> None:
    if event.organizer_email and event.organizer_email.lower() == str(settings.TEAMS_CALENDAR_MAILBOX).lower():
        return
    if settings.TEAMS_CALENDAR_SKIP_RECURRING and event.is_recurring:
        return
    now = datetime.now(timezone.utc)
    join_at = event.start_at if event.start_at > now else None
    meeting = await Meeting.find_by_calendar_event_id(event.event_id)
    if meeting is None:
        recipient = event.organizer_email if is_allowed_recipient(event.organizer_email) else None
        meeting = await Meeting.create_from_calendar(
            event.event_id, event.title, event.meeting_url, recipient, join_at, event.end_at
        )
        if meeting is None:
            return
    elif meeting.status == MeetingStatus.FAILED.value and not meeting.bot_id:
        meeting = await Meeting.claim_failed_calendar_event(
            event.event_id, event.title, event.meeting_url, join_at, event.end_at
        )
        if meeting is None:
            return
    else:
        if meeting.status != MeetingStatus.SCHEDULED.value or not meeting.bot_id:
            return
        if (meeting.title, meeting.meeting_url, meeting.join_at, meeting.calendar_end_at) == (
            event.title, event.meeting_url, event.start_at, event.end_at
        ):
            return
        if join_at is None:
            await delete_scheduled_bot(meeting.bot_id)
            await meeting.clear_calendar_bot("Rescheduling the Teams calendar bot")
        else:
            await update_scheduled_bot(meeting.bot_id, event.meeting_url, join_at)
            await meeting.update_calendar_details(event.title, event.meeting_url, join_at, event.end_at)
            logger.info("Updated bot for Teams calendar event %s", event.event_id)
            return
    if meeting.bot_id is None:
        try:
            bot = await create_bot(build_bot_payload(str(meeting.meeting_id), event.meeting_url, join_at))
        except ExternalServiceException:
            await meeting.mark_status(MeetingStatus.FAILED, "Could not schedule the calendar bot")
            raise
        await meeting.set_bot(bot.id, bot.state)
        await meeting.update_calendar_details(event.title, event.meeting_url, join_at, event.end_at)
        if join_at is None:
            await meeting.mark_status(MeetingStatus.JOINING)
        logger.info("Scheduled bot for Teams calendar event %s", event.event_id)


async def sync_teams_calendar() -> None:
    events, event_ids, window_start, window_end = await list_calendar_events()
    for event in events:
        try:
            await _schedule_event(event)
        except Exception:
            logger.exception("Could not schedule one Teams calendar event")
    scheduled = await Meeting.list_scheduled_calendar_meetings(window_start, window_end)
    for meeting in scheduled:
        if meeting.calendar_event_id in event_ids or not meeting.bot_id:
            continue
        try:
            await delete_scheduled_bot(meeting.bot_id)
            await meeting.clear_calendar_bot("Teams calendar invitation was cancelled or removed")
            logger.info("Removed bot for cancelled Teams calendar event %s", meeting.calendar_event_id)
        except Exception:
            logger.exception("Could not remove a cancelled Teams calendar bot")


async def run_teams_calendar_sync() -> None:
    while True:
        try:
            await sync_teams_calendar()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Teams calendar sync failed")
        await asyncio.sleep(settings.TEAMS_CALENDAR_POLL_SECONDS)
