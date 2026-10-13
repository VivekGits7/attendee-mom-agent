from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status

from app.attendee import AttendeeWebhookEnvelope, verify_attendee_signature
from app.common import (
    COMMON_ERROR_RESPONSES,
    BadGatewayResponse,
    BadRequestResponse,
    BaseResponse,
    ConflictResponse,
    NotFoundResponse,
    SortOrder,
)
from app.config import settings
from app.dependencies import require_api_key
from app.error import (
    AppException,
    BadRequestException,
    UnauthorizedException,
    validate_uuid,
)
from app.limiter import limiter
from app.logger import get_logger
from app.meeting.enums import MeetingPlatform, MeetingSortBy, MeetingStatus
from app.meeting.schemas import (
    CreateMeetingRequest,
    CreateMeetingResponse,
    MeetingActionResponse,
    MeetingDetailResponse,
    MeetingListResponse,
)
from app.meeting.service import (
    create_meeting,
    get_meeting_detail,
    handle_attendee_webhook,
    list_meetings,
    regenerate_minutes,
    request_bot_leave,
)

logger = get_logger(__name__)

meeting_router = APIRouter(
    prefix="/api/meetings", tags=["Meetings"], dependencies=[Depends(require_api_key)]
)
webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@meeting_router.get(
    "",
    response_model=MeetingListResponse,
    summary="List meetings",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": MeetingListResponse, "description": "Filtered meeting page"},
    },
)
@limiter.limit("30/minute")
async def list_meetings_endpoint(
    request: Request,
    search: Optional[str] = Query(None, max_length=100, description="Search meeting title or recipient email"),
    status: Optional[MeetingStatus] = Query(None, description="Filter by meeting pipeline status"),
    platform: Optional[MeetingPlatform] = Query(None, description="Filter by meeting platform"),
    sort_by: MeetingSortBy = Query(MeetingSortBy.TITLE, description="Field used for alphabetical sorting"),
    sort_order: SortOrder = Query(SortOrder.LATEST, description="Sort as latest, oldest, a_to_z, or z_to_a"),
    limit: int = Query(20, ge=1, le=100, description="Meetings per page"),
    offset: int = Query(0, ge=0, description="Meetings skipped before this page"),
) -> MeetingListResponse:
    """
    List saved meetings with filters and pagination.

    - **search**: optional partial match on title or recipient email
    - **status**: optional, scheduled, joining, in_progress, processing, completed, or failed
    - **platform**: optional, google_meet or teams
    - **sort_by**: title, status, or created_at, used with alphabetical sort
    - **sort_order**: latest, oldest, a_to_z, or z_to_a, defaults to latest
    - **limit**: 1 to 100 meetings per page, defaults to 20
    - **offset**: number of matching meetings to skip, defaults to 0
    - header **X-API-Key** is required
    """
    try:
        meetings, total = await list_meetings(
            search, status, platform, sort_by, sort_order, limit, offset
        )
        return MeetingListResponse(
            success=True,
            message="Meetings retrieved successfully",
            data=meetings,
            total=total,
            limit=limit,
            offset=offset,
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"List meetings error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@meeting_router.post(
    "",
    response_model=CreateMeetingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send the notetaker bot to a meeting",
    responses={
        **COMMON_ERROR_RESPONSES,
        201: {
            "model": CreateMeetingResponse,
            "description": "Meeting saved and bot created",
        },
        400: {"model": BadRequestResponse, "description": "Invalid input"},
        502: {
            "model": BadGatewayResponse,
            "description": "Attendee refused or could not be reached",
        },
    },
)
@limiter.limit("20/minute")
async def create_meeting_endpoint(
    request: Request, data: CreateMeetingRequest
) -> CreateMeetingResponse:
    """
    Save a meeting and send the notetaker bot to it.

    - **meeting_url**: required, a Google Meet or Microsoft Teams link
    - **title**: required, 2 to 255 chars, used in the minutes email subject
    - **recipient_email**: optional, gets the minutes when it is on an allowed domain, otherwise the default address is used
    - **join_at**: optional, ISO 8601 with timezone, the bot joins at this time, empty means join now
    - header **X-API-Key** is required
    - the bot leaves on its own 30 seconds after everyone else leaves
    """
    try:
        meeting = await create_meeting(data)
        message = (
            "Bot scheduled for the meeting"
            if data.join_at
            else "Bot is on its way to the meeting"
        )
        return CreateMeetingResponse(success=True, message=message, data=meeting)
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Create meeting error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@meeting_router.get(
    "/{meeting_id}",
    response_model=MeetingDetailResponse,
    summary="Get a meeting with transcript and minutes",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": MeetingDetailResponse, "description": "Meeting found"},
        400: {"model": BadRequestResponse, "description": "Malformed meeting_id"},
        404: {"model": NotFoundResponse, "description": "Meeting not found"},
    },
)
@limiter.limit("60/minute")
async def get_meeting_endpoint(
    request: Request, meeting_id: str
) -> MeetingDetailResponse:
    """
    Get one meeting with its speaker named transcript and minutes.

    - **meeting_id**: the meeting UUID, passed in the path
    - transcript lines fill in live while the meeting runs
    - minutes stay empty until status is completed
    - header **X-API-Key** is required
    """
    try:
        validate_uuid((meeting_id, "meeting_id"))
        meeting = await get_meeting_detail(meeting_id)
        return MeetingDetailResponse(
            success=True, message="Meeting retrieved successfully", data=meeting
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Get meeting error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@meeting_router.post(
    "/{meeting_id}/leave",
    response_model=MeetingActionResponse,
    summary="Make the bot leave now",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": MeetingActionResponse, "description": "Bot asked to leave"},
        400: {"model": BadRequestResponse, "description": "Malformed meeting_id"},
        404: {"model": NotFoundResponse, "description": "Meeting not found"},
        409: {"model": ConflictResponse, "description": "Bot already left"},
        502: {
            "model": BadGatewayResponse,
            "description": "Attendee refused or could not be reached",
        },
    },
)
@limiter.limit("10/minute")
async def leave_meeting_endpoint(
    request: Request, meeting_id: str
) -> MeetingActionResponse:
    """
    Make the bot leave the meeting right away.

    - **meeting_id**: the meeting UUID, passed in the path
    - minutes and email follow automatically once Attendee reports the bot ended
    - header **X-API-Key** is required
    """
    try:
        validate_uuid((meeting_id, "meeting_id"))
        meeting = await request_bot_leave(meeting_id)
        return MeetingActionResponse(
            success=True, message="Bot asked to leave the meeting", data=meeting
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Leave meeting error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@meeting_router.post(
    "/{meeting_id}/minutes",
    response_model=MeetingActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Regenerate minutes and resend the email",
    responses={
        **COMMON_ERROR_RESPONSES,
        202: {"model": MeetingActionResponse, "description": "Minutes job started"},
        400: {"model": BadRequestResponse, "description": "Malformed meeting_id"},
        404: {"model": NotFoundResponse, "description": "Meeting not found"},
        409: {"model": ConflictResponse, "description": "Meeting has not ended yet"},
    },
)
@limiter.limit("5/minute")
async def regenerate_minutes_endpoint(
    request: Request, meeting_id: str, background_tasks: BackgroundTasks
) -> MeetingActionResponse:
    """
    Pull the final transcript again, rebuild the minutes and email them again.

    - **meeting_id**: the meeting UUID, passed in the path
    - works only after the bot ended
    - sends the email again
    - header **X-API-Key** is required
    """
    try:
        validate_uuid((meeting_id, "meeting_id"))
        meeting = await regenerate_minutes(meeting_id, background_tasks)
        return MeetingActionResponse(
            success=True, message="Minutes are being generated", data=meeting
        )
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Regenerate minutes error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@webhook_router.post(
    "/attendee",
    response_model=BaseResponse,
    summary="Receive Attendee webhooks",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": BaseResponse, "description": "Webhook accepted"},
        400: {
            "model": BadRequestResponse,
            "description": "Body is not a valid Attendee webhook",
        },
    },
)
@limiter.limit(settings.WEBHOOK_RATE_LIMIT)
async def attendee_webhook_endpoint(
    request: Request, background_tasks: BackgroundTasks
) -> BaseResponse:
    """
    Receive live transcript lines and bot state changes from Attendee.

    - called by Attendee through the ngrok URL, not by the frontend
    - header **X-Webhook-Signature** is required, base64 HMAC SHA256 of the body
    - trigger transcript.update stores one line with its speaker name
    - trigger bot.state_change with new_state ended or fatal_error starts the minutes and email job
    - repeated deliveries with the same idempotency_key are ignored
    """
    try:
        try:
            body = await request.json()
        except ValueError:
            raise BadRequestException("Webhook body must be valid JSON")
        if not isinstance(body, dict):
            raise BadRequestException("Webhook body must be a JSON object")
        if not verify_attendee_signature(
            body, request.headers.get("X-Webhook-Signature")
        ):
            raise UnauthorizedException("Invalid webhook signature")
        try:
            envelope = AttendeeWebhookEnvelope.model_validate(body)
        except ValueError:
            raise BadRequestException("Webhook body is missing required fields")
        await handle_attendee_webhook(envelope, background_tasks)
        return BaseResponse(success=True, message="Webhook received")
    except (HTTPException, AppException):
        raise
    except Exception as e:
        logger.error(f"Attendee webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
