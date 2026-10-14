from enum import Enum


class MeetingPlatform(str, Enum):
    GOOGLE_MEET = "google_meet"
    TEAMS = "teams"


class MeetingStatus(str, Enum):
    SCHEDULED = "scheduled"
    JOINING = "joining"
    IN_PROGRESS = "in_progress"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SENT_TO_FALLBACK = "sent_to_fallback"
    FAILED = "failed"


class UtteranceSource(str, Enum):
    REALTIME = "realtime"
    FINAL = "final"


class MeetingSortBy(str, Enum):
    TITLE = "title"
    STATUS = "status"
    CREATED_AT = "created_at"


class NoTranscriptReason(str, Enum):
    NOBODY_JOINED = "Nobody else joined the meeting while the bot was there"
    NO_WORDS = "The bot heard the meeting but no words came through. Check that speakers were unmuted and their mic was loud enough"
    TRANSCRIPTION_FAILED = "Transcription failed in the meeting bot service. Check the transcription provider key in Attendee"
    UNKNOWN = "No transcript came back from the meeting bot service"
