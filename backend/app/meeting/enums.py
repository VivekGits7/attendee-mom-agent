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
