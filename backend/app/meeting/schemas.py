from datetime import datetime, timezone
from typing import List, Optional

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
    "recipient_email": "vivek@tcg.com",
    "join_at": None,
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
            "owner": "Vivek Vishwakarma",
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
        examples=["vivek@tcg.com"],
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
                "recipient_email": "vivek@tcg.com",
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
        None, description="Requested recipient", examples=["vivek@tcg.com"]
    )
    join_at: Optional[str] = Field(
        None, description="Scheduled join time", examples=["2026-10-12T10:00:00+00:00"]
    )
    email_status: EmailStatus = Field(
        ..., description="Minutes email status", examples=["pending"]
    )
    email_sent_to: Optional[str] = Field(
        None, description="Address the minutes went to", examples=["vivek@tcg.com"]
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
    speaker_name: str = Field(
        ..., description="Speaker name", examples=["Vivek Vishwakarma"]
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
                    "email_sent_to": "vivek@tcg.com",
                    "utterances": [
                        {
                            "speaker_name": "Vivek Vishwakarma",
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
