from enum import Enum


class AttendeeTrigger(str, Enum):
    BOT_STATE_CHANGE = "bot.state_change"
    TRANSCRIPT_UPDATE = "transcript.update"


class AttendeeBotState(str, Enum):
    READY = "ready"
    SCHEDULED = "scheduled"
    STAGED = "staged"
    JOINING = "joining"
    WAITING_ROOM = "waiting_room"
    JOINED_NOT_RECORDING = "joined_not_recording"
    JOINED_RECORDING = "joined_recording"
    JOINED_RECORDING_PAUSED = "joined_recording_paused"
    JOINED_RECORDING_PERMISSION_DENIED = "joined_recording_permission_denied"
    LEAVING = "leaving"
    POST_PROCESSING = "post_processing"
    FATAL_ERROR = "fatal_error"
    ENDED = "ended"
    DATA_DELETED = "data_deleted"


class AttendeeTranscriptionState(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


class TranscriptionProvider(str, Enum):
    CLOSED_CAPTIONS = "closed_captions"
    DEEPGRAM = "deepgram"
    OPENAI = "openai"
