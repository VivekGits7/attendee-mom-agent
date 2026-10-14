import uuid
from datetime import datetime
from typing import List, Optional

from app.attendee import AttendeeUtterance
from app.common import SortOrder
from app.database import (
    execute_command,
    execute_command_with_return,
    execute_query,
    execute_query_one,
    get_pool,
)
from app.meeting.enums import (
    EmailStatus,
    MeetingPlatform,
    MeetingSortBy,
    MeetingStatus,
    UtteranceSource,
)

FINISHED_STATUSES = (
    MeetingStatus.PROCESSING.value,
    MeetingStatus.COMPLETED.value,
    MeetingStatus.FAILED.value,
)

# SQL
_INSERT_UTTERANCE = """
    INSERT INTO meeting_utterances (
        meeting_utterance_id, meeting_id, speaker_name, speaker_uuid, speaker_user_uuid,
        speaker_is_host, timestamp_ms, duration_ms, text, source
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
"""

_LIST_COLUMNS = """
    meeting_id, title, meeting_url, platform, bot_id, bot_state, status,
    recipient_email, join_at, email_status, email_sent_to, error_message, created_at
"""

_SORT_COLUMNS = {
    MeetingSortBy.TITLE: "LOWER(title)",
    MeetingSortBy.STATUS: "status",
    MeetingSortBy.CREATED_AT: "created_at",
}


def _meeting_filters(
    search: Optional[str],
    status: Optional[MeetingStatus],
    platform: Optional[MeetingPlatform],
) -> tuple[str, list]:
    conditions: list[str] = []
    args: list = []
    if search:
        args.append(f"%{search.strip()}%")
        conditions.append(
            f"(title ILIKE ${len(args)} OR recipient_email ILIKE ${len(args)})"
        )
    if status:
        args.append(status.value)
        conditions.append(f"status = ${len(args)}")
    if platform:
        args.append(platform.value)
        conditions.append(f"platform = ${len(args)}")
    return " WHERE " + " AND ".join(conditions) if conditions else "", args


def _utterance_args(
    meeting_id: uuid.UUID, utterance: AttendeeUtterance, source: UtteranceSource
) -> tuple:
    return (
        uuid.uuid4(),
        meeting_id,
        utterance.speaker_name,
        utterance.speaker_uuid,
        utterance.speaker_user_uuid,
        utterance.speaker_is_host,
        utterance.timestamp_ms,
        utterance.duration_ms,
        utterance.text,
        source.value,
    )


class Meeting:
    def __init__(self, **kwargs):
        self.meeting_id = kwargs.get("meeting_id")
        self.title = kwargs.get("title")
        self.meeting_url = kwargs.get("meeting_url")
        self.platform = kwargs.get("platform")
        self.bot_id = kwargs.get("bot_id")
        self.bot_state = kwargs.get("bot_state")
        self.bot_state_changed_at = kwargs.get("bot_state_changed_at")
        self.status = kwargs.get("status")
        self.recipient_email = kwargs.get("recipient_email")
        self.join_at = kwargs.get("join_at")
        self.minutes = kwargs.get("minutes")
        self.email_status = kwargs.get("email_status")
        self.email_sent_to = kwargs.get("email_sent_to")
        self.error_message = kwargs.get("error_message")
        self.ended_at = kwargs.get("ended_at")
        self.created_at = kwargs.get("created_at")
        self.updated_at = kwargs.get("updated_at")

    @classmethod
    async def create(
        cls,
        title: str,
        meeting_url: str,
        platform: MeetingPlatform,
        recipient_email: Optional[str],
        join_at,
    ) -> "Meeting":
        status = MeetingStatus.SCHEDULED if join_at else MeetingStatus.JOINING
        row = await execute_command_with_return(
            # SQL
            """
            INSERT INTO meetings (meeting_id, title, meeting_url, platform, status, recipient_email, join_at, email_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            uuid.uuid4(),
            title,
            meeting_url,
            platform.value,
            status.value,
            recipient_email,
            join_at,
            EmailStatus.PENDING.value,
        )
        return cls(**dict(row))

    @classmethod
    async def find_by_id(cls, meeting_id: str) -> Optional["Meeting"]:
        row = await execute_query_one(
            "SELECT * FROM meetings WHERE meeting_id = $1", uuid.UUID(meeting_id)
        )
        return cls(**dict(row)) if row else None

    @classmethod
    async def find_by_bot_id(cls, bot_id: str) -> Optional["Meeting"]:
        row = await execute_query_one(
            "SELECT * FROM meetings WHERE bot_id = $1", bot_id
        )
        return cls(**dict(row)) if row else None

    @classmethod
    async def list_page(
        cls,
        search: Optional[str],
        status: Optional[MeetingStatus],
        platform: Optional[MeetingPlatform],
        sort_by: MeetingSortBy,
        sort_order: SortOrder,
        limit: int,
        offset: int,
    ) -> tuple[List["Meeting"], int]:
        where, args = _meeting_filters(search, status, platform)
        total_row = await execute_query_one(
            f"SELECT COUNT(*) AS total FROM meetings{where}", *args
        )
        if sort_order == SortOrder.LATEST:
            ordering = "created_at DESC"
        elif sort_order == SortOrder.OLDEST:
            ordering = "created_at ASC"
        else:
            direction = "ASC" if sort_order == SortOrder.A_TO_Z else "DESC"
            ordering = f"{_SORT_COLUMNS[sort_by]} {direction}"
        rows = await execute_query(
            f"SELECT {_LIST_COLUMNS} FROM meetings{where} "
            f"ORDER BY {ordering} NULLS LAST, meeting_id "
            f"LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}",
            *args,
            limit,
            offset,
        )
        return [cls(**dict(row)) for row in rows], int(total_row["total"])

    @classmethod
    async def claim_for_processing(cls, meeting_id: uuid.UUID) -> bool:
        row = await execute_command_with_return(
            # SQL
            """
            UPDATE meetings
            SET status = $2, ended_at = COALESCE(ended_at, NOW()), updated_at = NOW()
            WHERE meeting_id = $1 AND status NOT IN ($2, $3)
            RETURNING meeting_id
            """,
            meeting_id,
            MeetingStatus.PROCESSING.value,
            MeetingStatus.COMPLETED.value,
        )
        return row is not None

    async def set_bot(self, bot_id: str, bot_state: Optional[str]) -> None:
        # The first webhook can land before this write, so keep any state it already stored.
        row = await execute_command_with_return(
            # SQL
            """
            UPDATE meetings
            SET bot_id = $2,
                bot_state = CASE WHEN bot_state_changed_at IS NULL THEN $3 ELSE bot_state END,
                updated_at = NOW()
            WHERE meeting_id = $1
            RETURNING bot_state
            """,
            self.meeting_id,
            bot_id,
            bot_state,
        )
        self.bot_id = bot_id
        self.bot_state = row["bot_state"] if row else bot_state

    async def update_progress(
        self,
        bot_state: str,
        status: Optional[MeetingStatus],
        changed_at: Optional[datetime] = None,
    ) -> bool:
        # Webhooks can arrive out of order, so a change older than the stored one is skipped.
        row = await execute_command_with_return(
            # SQL
            """
            UPDATE meetings
            SET bot_state = $2,
                bot_state_changed_at = COALESCE($7::timestamptz, bot_state_changed_at),
                status = CASE WHEN $3::text IS NOT NULL AND status NOT IN ($4, $5, $6) THEN $3::text ELSE status END,
                updated_at = NOW()
            WHERE meeting_id = $1
              AND ($7::timestamptz IS NULL OR bot_state_changed_at IS NULL OR bot_state_changed_at <= $7::timestamptz)
            RETURNING meeting_id
            """,
            self.meeting_id,
            bot_state,
            status.value if status else None,
            *FINISHED_STATUSES,
            changed_at,
        )
        if row is None:
            return False
        self.bot_state = bot_state
        return True

    async def mark_status(
        self, status: MeetingStatus, error_message: Optional[str] = None
    ) -> None:
        await execute_command(
            "UPDATE meetings SET status = $2, error_message = $3, updated_at = NOW() WHERE meeting_id = $1",
            self.meeting_id,
            status.value,
            error_message,
        )
        self.status, self.error_message = status.value, error_message

    async def save_minutes(self, minutes: dict) -> None:
        await execute_command(
            "UPDATE meetings SET minutes = $2, updated_at = NOW() WHERE meeting_id = $1",
            self.meeting_id,
            minutes,
        )
        self.minutes = minutes

    async def set_email_result(
        self, email_status: EmailStatus, email_sent_to: Optional[str]
    ) -> None:
        await execute_command(
            "UPDATE meetings SET email_status = $2, email_sent_to = $3, updated_at = NOW() WHERE meeting_id = $1",
            self.meeting_id,
            email_status.value,
            email_sent_to,
        )
        self.email_status, self.email_sent_to = email_status.value, email_sent_to

    def to_dict(self) -> dict:
        return {
            "meeting_id": str(self.meeting_id),
            "title": self.title,
            "meeting_url": self.meeting_url,
            "platform": self.platform,
            "bot_id": self.bot_id,
            "bot_state": self.bot_state,
            "status": self.status,
            "recipient_email": self.recipient_email,
            "join_at": self.join_at.isoformat() if self.join_at else None,
            "minutes": self.minutes,
            "email_status": self.email_status,
            "email_sent_to": self.email_sent_to,
            "error_message": self.error_message,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_public_dict(self) -> dict:
        data = self.to_dict()
        data.pop("minutes")
        data.pop("ended_at")
        return data


class MeetingUtterance:
    def __init__(self, **kwargs):
        self.meeting_utterance_id = kwargs.get("meeting_utterance_id")
        self.meeting_id = kwargs.get("meeting_id")
        self.speaker_name = kwargs.get("speaker_name")
        self.speaker_uuid = kwargs.get("speaker_uuid")
        self.speaker_is_host = kwargs.get("speaker_is_host")
        self.timestamp_ms = kwargs.get("timestamp_ms")
        self.duration_ms = kwargs.get("duration_ms")
        self.text = kwargs.get("text")
        self.source = kwargs.get("source")

    @classmethod
    async def upsert(
        cls,
        meeting_id: uuid.UUID,
        utterance: AttendeeUtterance,
        source: UtteranceSource,
    ) -> None:
        await execute_command(
            _INSERT_UTTERANCE
            # SQL
            + """
            ON CONFLICT (meeting_id, speaker_uuid, timestamp_ms)
            DO UPDATE SET text = EXCLUDED.text, duration_ms = EXCLUDED.duration_ms,
                speaker_name = EXCLUDED.speaker_name, source = EXCLUDED.source, updated_at = NOW()
            """,
            *_utterance_args(meeting_id, utterance, source),
        )

    @classmethod
    async def replace_all(
        cls, meeting_id: uuid.UUID, utterances: List[AttendeeUtterance]
    ) -> None:
        async with get_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "DELETE FROM meeting_utterances WHERE meeting_id = $1", meeting_id
                )
                await conn.executemany(
                    _INSERT_UTTERANCE
                    + " ON CONFLICT (meeting_id, speaker_uuid, timestamp_ms) DO NOTHING",
                    [
                        _utterance_args(meeting_id, u, UtteranceSource.FINAL)
                        for u in utterances
                    ],
                )

    @classmethod
    async def list_by_meeting(cls, meeting_id: uuid.UUID) -> List["MeetingUtterance"]:
        rows = await execute_query(
            "SELECT * FROM meeting_utterances WHERE meeting_id = $1 ORDER BY timestamp_ms, meeting_utterance_id",
            meeting_id,
        )
        return [cls(**dict(row)) for row in rows]

    def to_dict(self) -> dict:
        return {
            "speaker_name": self.speaker_name,
            "speaker_is_host": self.speaker_is_host,
            "timestamp_ms": self.timestamp_ms,
            "duration_ms": self.duration_ms,
            "text": self.text,
        }

    def to_public_dict(self) -> dict:
        return self.to_dict()


class AttendeeWebhookEvent:
    @classmethod
    async def record(
        cls, idempotency_key: uuid.UUID, bot_id: Optional[str], trigger_type: str
    ) -> bool:
        row = await execute_command_with_return(
            # SQL
            """
            INSERT INTO attendee_webhook_events (attendee_webhook_event_id, idempotency_key, bot_id, trigger_type)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING attendee_webhook_event_id
            """,
            uuid.uuid4(),
            idempotency_key,
            bot_id,
            trigger_type,
        )
        return row is not None

    @classmethod
    async def forget(cls, idempotency_key: uuid.UUID) -> None:
        await execute_command(
            "DELETE FROM attendee_webhook_events WHERE idempotency_key = $1",
            idempotency_key,
        )
