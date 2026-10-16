from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.common import BaseResponse
from app.meeting.enums import EmailStatus, MeetingPlatform, MeetingStatus
from app.meeting.utils import detect_platform
from app.mom import MeetingMinutes

MEETING_EXAMPLE = {
    "meeting_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "Sprint planning",
    "meeting_url": "https://meet.google.com/abc-defg-hij",
    "platform": "google_meet",
    "bot_id": "bot_3hfP0PXEsNinIZmh",
    "bot_state": "joining",
    "status": "joining",
    "recipient_email": "tcg@tcgdigital.com",
    "join_at": None,
    "ends_at": None,
    "calendar_synced": False,
    "email_status": "pending",
    "email_sent_to": None,
    "error_message": None,
    "created_at": "2026-10-11T10:30:00+00:00",
}

MINUTES_EXAMPLE = {
    "summary": "The team reviewed sprint scope and agreed to move the release by one week.",
    "outcomes": [
        {
            "item": "Share the API contract with the frontend team",
            "owner": "TCG User",
            "due_date": "Friday",
        },
        {"item": "Move the release by one week", "owner": None, "due_date": None},
    ],
    "open_questions": ["Who owns the QA sign off"],
}


class CreateMeetingRequest(BaseModel):
    meeting_url: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Google Meet or Teams meeting link",
        examples=["https://meet.google.com/abc-defg-hij"],
    )
    title: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Meeting title used in the minutes email",
        examples=["Sprint planning"],
    )
    recipient_email: Optional[EmailStr] = Field(
        default=None,
        description="Who gets the minutes, must be on an allowed domain",
        examples=["tcg@tcgdigital.com"],
    )
    join_at: Optional[datetime] = Field(
        default=None,
        description="When the bot joins, ISO 8601 with timezone, empty means now",
        examples=["2026-10-12T10:00:00Z"],
    )

    @field_validator("meeting_url")
    @classmethod
    def validate_meeting_url(cls, v: str) -> str:
        v = v.strip()
        if detect_platform(v) is None:
            raise ValueError("Only Google Meet and Microsoft Teams links are supported")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v

    @field_validator("join_at")
    @classmethod
    def validate_join_at(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError(
                "join_at must include a timezone, for example 2026-10-12T10:00:00Z"
            )
        if v <= datetime.now(timezone.utc):
            raise ValueError("join_at must be in the future")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "title": "Sprint planning",
                "recipient_email": "tcg@tcgdigital.com",
                "join_at": "2026-10-12T10:00:00Z",
            }
        }
    )


class MeetingData(BaseModel):
    meeting_id: str = Field(
        ...,
        description="Meeting UUID",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    title: str = Field(..., description="Meeting title", examples=["Sprint planning"])
    meeting_url: str = Field(
        ...,
        description="Meeting link",
        examples=["https://meet.google.com/abc-defg-hij"],
    )
    platform: MeetingPlatform = Field(
        ..., description="Meeting platform", examples=["google_meet"]
    )
    bot_id: Optional[str] = Field(
        None,
        description="Attendee bot id, empty until the bot is created",
        examples=["bot_3hfP0PXEsNinIZmh"],
    )
    bot_state: Optional[str] = Field(
        None, description="Latest bot state from Attendee", examples=["joining"]
    )
    status: MeetingStatus = Field(
        ..., description="Pipeline status", examples=["joining"]
    )
    recipient_email: Optional[str] = Field(
        None, description="Requested recipient", examples=["tcg@tcgdigital.com"]
    )
    join_at: Optional[str] = Field(
        None, description="Scheduled join time", examples=["2026-10-12T10:00:00+00:00"]
    )
    ends_at: Optional[str] = Field(
        None,
        description="Calendar event end time",
        examples=["2026-10-12T10:30:00+00:00"],
    )
    calendar_synced: bool = Field(
        ...,
        description="Whether the meeting came from the Teams calendar",
        examples=[False],
    )
    email_status: EmailStatus = Field(
        ..., description="Minutes email status", examples=["pending"]
    )
    email_sent_to: Optional[str] = Field(
        None, description="Address the minutes went to", examples=["tcg@tcgdigital.com"]
    )
    error_message: Optional[str] = Field(
        None,
        description="Why the pipeline failed",
        examples=["Nobody else joined the meeting while the bot was there"],
    )
    created_at: str = Field(
        ..., description="Creation time", examples=["2026-10-11T10:30:00+00:00"]
    )


class UtteranceData(BaseModel):
    utterance_id: str = Field(
        ...,
        description="Line UUID, stays the same when a live line is updated",
        examples=["9b2e4c1a-6f0d-4a8e-b6f1-2d7c5e8a9f30"],
    )
    speaker_name: str = Field(
        ..., description="Speaker name", examples=["TCG User"]
    )
    speaker_is_host: bool = Field(
        ..., description="Whether the speaker is the host", examples=[True]
    )
    timestamp_ms: int = Field(
        ...,
        description="Unix time in ms when the line started",
        examples=[1791887310881],
    )
    duration_ms: int = Field(..., description="Utterance length in ms", examples=[7710])
    text: str = Field(
        ...,
        description="What was said",
        examples=["Let's lock the sprint scope today."],
    )


class MeetingDetailData(MeetingData):
    utterances: List[UtteranceData] = Field(
        ..., description="Transcript lines in order"
    )
    minutes: Optional[MeetingMinutes] = Field(
        None, description="Generated minutes, empty until the meeting is processed"
    )


class CreateMeetingResponse(BaseResponse):
    data: MeetingData = Field(..., description="Created meeting")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Bot is on its way to the meeting",
                "data": MEETING_EXAMPLE,
            }
        }
    )


class MeetingDetailResponse(BaseResponse):
    data: MeetingDetailData = Field(
        ..., description="Meeting with transcript and minutes"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Meeting retrieved successfully",
                "data": {
                    **MEETING_EXAMPLE,
                    "bot_state": "ended",
                    "status": "completed",
                    "email_status": "sent",
                    "email_sent_to": "tcg@tcgdigital.com",
                    "utterances": [
                        {
                            "utterance_id": "9b2e4c1a-6f0d-4a8e-b6f1-2d7c5e8a9f30",
                            "speaker_name": "TCG User",
                            "speaker_is_host": True,
                            "timestamp_ms": 1791887310881,
                            "duration_ms": 7710,
                            "text": "Let's lock the sprint scope today.",
                        }
                    ],
                    "minutes": MINUTES_EXAMPLE,
                },
            }
        }
    )


class MeetingListResponse(BaseResponse):
    data: List[MeetingData] = Field(..., description="Meetings on this page")
    total: int = Field(
        ..., description="Total meetings matching the filters", examples=[42]
    )
    limit: int = Field(..., description="Maximum meetings on this page", examples=[20])
    offset: int = Field(
        ..., description="Meetings skipped before this page", examples=[0]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Meetings retrieved successfully",
                "data": [MEETING_EXAMPLE],
                "total": 42,
                "limit": 20,
                "offset": 0,
            }
        }
    )


class MeetingActionResponse(BaseResponse):
    data: MeetingData = Field(..., description="Meeting after the action")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Bot asked to leave the meeting",
                "data": {**MEETING_EXAMPLE, "bot_state": "leaving"},
            }
        }
    )


LIVE_UTTERANCE_EXAMPLE = {
    "utterance_id": "9b2e4c1a-6f0d-4a8e-b6f1-2d7c5e8a9f30",
    "speaker_name": "TCG User",
    "speaker_is_host": True,
    "timestamp_ms": 1791887310881,
    "duration_ms": 7710,
    "text": "Let's lock the sprint scope today.",
}


class LiveTranscriptData(BaseModel):
    meeting: MeetingData = Field(..., description="Meeting details at the time of the snapshot")
    utterances: List[UtteranceData] = Field(..., description="Every transcript line so far, in order")


class WSSnapshotMessage(BaseModel):
    type: Literal["snapshot"] = Field("snapshot", description="Full transcript, replace what the client shows")
    data: LiveTranscriptData = Field(..., description="Meeting and transcript")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "snapshot",
                "data": {
                    "meeting": {**MEETING_EXAMPLE, "status": "in_progress", "bot_state": "joined_recording"},
                    "utterances": [LIVE_UTTERANCE_EXAMPLE],
                },
            }
        }
    )


class WSUtteranceMessage(BaseModel):
    type: Literal["utterance"] = Field("utterance", description="A new line, or an update to a line with the same utterance_id")
    data: UtteranceData = Field(..., description="Transcript line")

    model_config = ConfigDict(
        json_schema_extra={"example": {"type": "utterance", "data": LIVE_UTTERANCE_EXAMPLE}}
    )


class WSStatusMessage(BaseModel):
    type: Literal["status"] = Field("status", description="Meeting status, bot state or email status changed")
    data: MeetingData = Field(..., description="Meeting details after the change")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"type": "status", "data": {**MEETING_EXAMPLE, "status": "completed", "bot_state": "ended"}}
        }
    )


class WSPingMessage(BaseModel):
    type: Literal["ping"] = Field("ping", description="Keep alive, nothing to do")

    model_config = ConfigDict(json_schema_extra={"example": {"type": "ping"}})


class WSFailedMessage(BaseModel):
    type: Literal["failed"] = Field("failed", description="The socket is about to close")
    message: str = Field(..., description="Why the socket is closing", examples=["Please log in to continue"])

    model_config = ConfigDict(
        json_schema_extra={"example": {"type": "failed", "message": "Please log in to continue"}}
    )
