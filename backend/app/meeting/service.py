import asyncio
from typing import List, Optional

from fastapi import BackgroundTasks

from app.common import SortOrder
from app.attendee import (
    AttendeeBotState,
    AttendeeStateChange,
    AttendeeTranscriptionState,
    AttendeeTrigger,
    AttendeeUtterance,
    AttendeeWebhookEnvelope,
    build_bot_payload,
    create_bot,
    get_bot,
    get_transcript,
    leave_bot,
)
from app.config import settings
from app.error import (
    ConflictException,
    ExternalServiceException,
    NotFoundException,
    get_user_friendly_message,
)
from app.logger import get_logger
from app.mail import is_allowed_recipient, send_email
from app.meeting.enums import (
    EmailStatus,
    MeetingPlatform,
    MeetingSortBy,
    MeetingStatus,
    UtteranceSource,
)
from app.meeting.model import AttendeeWebhookEvent, Meeting, MeetingUtterance
from app.meeting.schemas import (
    CreateMeetingRequest,
    MeetingData,
    MeetingDetailData,
    UtteranceData,
)
from app.meeting.utils import (
    build_transcript_text,
    detect_platform,
    is_valid_uuid,
    render_minutes_email,
)
from app.mom import MeetingMinutes, generate_minutes

logger = get_logger(__name__)

FINAL_BOT_STATES = {AttendeeBotState.ENDED.value, AttendeeBotState.FATAL_ERROR.value}
CLOSED_MEETING_STATUSES = {
    MeetingStatus.PROCESSING.value,
    MeetingStatus.COMPLETED.value,
}

BOT_STATE_TO_MEETING_STATUS = {
    AttendeeBotState.SCHEDULED.value: MeetingStatus.SCHEDULED,
    AttendeeBotState.STAGED.value: MeetingStatus.SCHEDULED,
    AttendeeBotState.READY.value: MeetingStatus.JOINING,
    AttendeeBotState.JOINING.value: MeetingStatus.JOINING,
    AttendeeBotState.WAITING_ROOM.value: MeetingStatus.JOINING,
    AttendeeBotState.JOINED_NOT_RECORDING.value: MeetingStatus.IN_PROGRESS,
    AttendeeBotState.JOINED_RECORDING.value: MeetingStatus.IN_PROGRESS,
    AttendeeBotState.JOINED_RECORDING_PAUSED.value: MeetingStatus.IN_PROGRESS,
    AttendeeBotState.JOINED_RECORDING_PERMISSION_DENIED.value: MeetingStatus.IN_PROGRESS,
}


async def list_meetings(
    search: Optional[str],
    status: Optional[MeetingStatus],
    platform: Optional[MeetingPlatform],
    sort_by: MeetingSortBy,
    sort_order: SortOrder,
    limit: int,
    offset: int,
) -> tuple[List[MeetingData], int]:
    meetings, total = await Meeting.list_page(
        search, status, platform, sort_by, sort_order, limit, offset
    )
    return [MeetingData(**meeting.to_public_dict()) for meeting in meetings], total


async def create_meeting(data: CreateMeetingRequest) -> MeetingData:
    meeting = await Meeting.create(
        data.title,
        data.meeting_url,
        detect_platform(data.meeting_url),
        data.recipient_email,
        data.join_at,
    )
    payload = build_bot_payload(str(meeting.meeting_id), data.meeting_url, data.join_at)
    try:
        bot = await create_bot(payload)
    except ExternalServiceException as e:
        await meeting.mark_status(MeetingStatus.FAILED, get_user_friendly_message(e))
        raise
    await meeting.set_bot(bot.id, bot.state)
    return MeetingData(**meeting.to_public_dict())


async def get_meeting_detail(meeting_id: str) -> MeetingDetailData:
    meeting = await _get_meeting_or_404(meeting_id)
    utterances = await MeetingUtterance.list_by_meeting(meeting.meeting_id)
    return MeetingDetailData(
        **meeting.to_public_dict(),
        utterances=[UtteranceData(**u.to_public_dict()) for u in utterances],
        minutes=MeetingMinutes.model_validate(meeting.minutes)
        if meeting.minutes
        else None,
    )


async def request_bot_leave(meeting_id: str) -> MeetingData:
    meeting = await _get_meeting_or_404(meeting_id)
    if not meeting.bot_id or meeting.bot_state in FINAL_BOT_STATES:
        raise ConflictException("The bot is not in this meeting anymore")
    await leave_bot(meeting.bot_id)
    await meeting.update_progress(AttendeeBotState.LEAVING.value, None)
    return MeetingData(**meeting.to_public_dict())


async def regenerate_minutes(
    meeting_id: str, background_tasks: BackgroundTasks
) -> MeetingData:
    meeting = await _get_meeting_or_404(meeting_id)
    if meeting.bot_state not in FINAL_BOT_STATES:
        raise ConflictException("Minutes can be generated only after the meeting ends")
    await meeting.mark_status(MeetingStatus.PROCESSING)
    background_tasks.add_task(finalize_meeting, str(meeting.meeting_id))
    return MeetingData(**meeting.to_public_dict())


async def handle_attendee_webhook(
    envelope: AttendeeWebhookEnvelope, background_tasks: BackgroundTasks
) -> None:
    if not await AttendeeWebhookEvent.record(
        envelope.idempotency_key, envelope.bot_id, envelope.trigger
    ):
        return
    try:
        meeting = await _find_meeting_for_webhook(envelope)
        if meeting is None:
            logger.warning(
                f"Webhook {envelope.trigger} for unknown bot {envelope.bot_id}"
            )
            return
        if envelope.trigger == AttendeeTrigger.TRANSCRIPT_UPDATE.value:
            await _store_live_utterance(meeting, envelope.data)
        elif envelope.trigger == AttendeeTrigger.BOT_STATE_CHANGE.value:
            await _apply_state_change(meeting, envelope.data, background_tasks)
    except Exception:
        # Let Attendee's retry reprocess this delivery instead of dropping it as a duplicate.
        await AttendeeWebhookEvent.forget(envelope.idempotency_key)
        raise


async def finalize_meeting(meeting_id: str) -> None:
    meeting: Optional[Meeting] = None
    try:
        meeting = await Meeting.find_by_id(meeting_id)
        if meeting is None:
            return

        await _sync_final_transcript(meeting)
        utterances = await MeetingUtterance.list_by_meeting(meeting.meeting_id)
        if not utterances:
            await meeting.mark_status(
                MeetingStatus.FAILED, "No speech was captured in this meeting"
            )
            return

        minutes = await generate_minutes(
            meeting.title, build_transcript_text(utterances)
        )
        await meeting.save_minutes(minutes.model_dump(mode="json"))
        await meeting.mark_status(MeetingStatus.COMPLETED)
        logger.info(f"Minutes ready for meeting {meeting_id}")

        try:
            await _deliver_minutes(meeting, minutes)
        except Exception as email_error:
            logger.error(f"Minutes email step failed for {meeting_id}: {email_error}")
            await meeting.set_email_result(EmailStatus.FAILED, None)

    except Exception as e:
        logger.error(f"Finalize failed for meeting {meeting_id}: {e}", exc_info=True)
        if meeting is not None:
            try:
                await meeting.mark_status(
                    MeetingStatus.FAILED, get_user_friendly_message(e)
                )
            except Exception as db_error:
                logger.error(
                    f"Could not mark meeting {meeting_id} as failed: {db_error}"
                )


async def _get_meeting_or_404(meeting_id: str) -> Meeting:
    meeting = await Meeting.find_by_id(meeting_id)
    if meeting is None:
        raise NotFoundException("Meeting not found")
    return meeting


async def _find_meeting_for_webhook(
    envelope: AttendeeWebhookEnvelope,
) -> Optional[Meeting]:
    meeting_id = (envelope.bot_metadata or {}).get("meeting_id")
    if is_valid_uuid(meeting_id):
        meeting = await Meeting.find_by_id(str(meeting_id))
        if meeting is not None:
            return meeting
    return await Meeting.find_by_bot_id(envelope.bot_id) if envelope.bot_id else None


async def _store_live_utterance(meeting: Meeting, data: dict) -> None:
    # The final transcript already holds every line, so late live lines would only add duplicates.
    if meeting.status in CLOSED_MEETING_STATUSES:
        return
    utterance = AttendeeUtterance.model_validate(data)
    if utterance.text:
        await MeetingUtterance.upsert(
            meeting.meeting_id, utterance, UtteranceSource.REALTIME
        )


async def _apply_state_change(
    meeting: Meeting, data: dict, background_tasks: BackgroundTasks
) -> None:
    change = AttendeeStateChange.model_validate(data)
    logger.info(
        f"Meeting {meeting.meeting_id} bot {change.old_state} -> {change.new_state} {change.event_sub_type or ''}"
    )
    await meeting.update_progress(
        change.new_state, BOT_STATE_TO_MEETING_STATUS.get(change.new_state)
    )

    if change.new_state in FINAL_BOT_STATES and await Meeting.claim_for_processing(
        meeting.meeting_id
    ):
        background_tasks.add_task(finalize_meeting, str(meeting.meeting_id))


async def _wait_for_final_transcript(bot_id: str) -> None:
    waited = 0
    while waited < settings.TRANSCRIPT_READY_MAX_WAIT_SECONDS:
        bot = await get_bot(bot_id)
        if bot.transcription_state != AttendeeTranscriptionState.IN_PROGRESS.value:
            return
        await asyncio.sleep(settings.TRANSCRIPT_READY_POLL_SECONDS)
        waited += settings.TRANSCRIPT_READY_POLL_SECONDS
    logger.warning(
        f"Transcript for bot {bot_id} still in progress after {waited}s, using what is available"
    )


async def _sync_final_transcript(meeting: Meeting) -> None:
    if not meeting.bot_id:
        return
    try:
        await _wait_for_final_transcript(meeting.bot_id)
        final_utterances: List[AttendeeUtterance] = [
            u for u in await get_transcript(meeting.bot_id) if u.text
        ]
    except ExternalServiceException:
        logger.warning(
            f"Final transcript fetch failed for {meeting.meeting_id}, falling back to live lines"
        )
        return
    if final_utterances:
        await MeetingUtterance.replace_all(meeting.meeting_id, final_utterances)


async def _deliver_minutes(meeting: Meeting, minutes: MeetingMinutes) -> None:
    subject, text_body, html_body = render_minutes_email(
        meeting.title, meeting.ended_at, minutes
    )
    fallback = settings.DEFAULT_MOM_EMAIL
    primary = (
        meeting.recipient_email
        if is_allowed_recipient(meeting.recipient_email)
        else fallback
    )

    try:
        await send_email(primary, subject, text_body, html_body)
        status = (
            EmailStatus.SENT if primary != fallback else EmailStatus.SENT_TO_FALLBACK
        )
        await meeting.set_email_result(status, primary)
        return
    except ExternalServiceException:
        if primary == fallback:
            await meeting.set_email_result(EmailStatus.FAILED, None)
            return

    logger.warning(
        f"Primary email failed for meeting {meeting.meeting_id}, sending to fallback"
    )
    try:
        await send_email(fallback, subject, text_body, html_body)
        await meeting.set_email_result(EmailStatus.SENT_TO_FALLBACK, fallback)
    except ExternalServiceException:
        await meeting.set_email_result(EmailStatus.FAILED, None)
