import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class AttendeeWebhookEnvelope(BaseModel):
    idempotency_key: uuid.UUID = Field(
        ..., description="Unique id of this delivery, used to drop retries"
    )
    bot_id: Optional[str] = Field(None, description="Attendee bot id")
    bot_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadata we attached when creating the bot"
    )
    trigger: str = Field(..., description="Webhook trigger name")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Trigger specific payload"
    )


class AttendeeUtterance(BaseModel):
    speaker_name: str = Field(..., description="Speaker display name from the meeting")
    speaker_uuid: str = Field(..., description="Speaker id inside the meeting")
    speaker_user_uuid: Optional[str] = Field(
        None, description="Platform user id when known"
    )
    speaker_is_host: bool = Field(
        default=False, description="Whether the speaker is the host"
    )
    timestamp_ms: int = Field(..., description="Unix time in ms when the line started")
    duration_ms: int = Field(default=0, description="Length of the utterance in ms")
    transcription: Optional[Dict[str, Any]] = Field(
        None, description="Attendee transcription object"
    )

    @property
    def text(self) -> str:
        return ((self.transcription or {}).get("transcript") or "").strip()


class AttendeeStateChange(BaseModel):
    event_type: Optional[str] = Field(None, description="Event that caused the change")
    event_sub_type: Optional[str] = Field(
        None, description="Detail such as auto leave only participant"
    )
    old_state: Optional[str] = Field(None, description="Previous bot state")
    new_state: str = Field(..., description="Current bot state")
    created_at: Optional[datetime] = Field(None, description="When the change happened")


class AttendeeBot(BaseModel):
    id: str = Field(..., description="Attendee bot id")
    state: Optional[str] = Field(None, description="Current bot state")
    transcription_state: Optional[str] = Field(
        None, description="Transcription state of the default recording"
    )
