import asyncio
import uuid
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.attendee import AttendeeWebhookEnvelope, verify_attendee_signature
from app.common import (
    COMMON_ERROR_RESPONSES,
    BadGatewayResponse,
    BadRequestResponse,
    BaseResponse,
    ConflictResponse,
    NotFoundResponse,
    SortOrder,
    WSCloseCode,
)
from app.config import settings
from app.dependencies import authenticate_ws, require_user_or_api_key
from app.error import (
    AppException,
    BadRequestException,
    NotFoundException,
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
    WSFailedMessage,
    WSPingMessage,
    WSSnapshotMessage,
)
from app.meeting.service import (
    create_meeting,
    get_live_snapshot,
    get_meeting_detail,
    handle_attendee_webhook,
    list_meetings,
    regenerate_minutes,
    request_bot_leave,
)
from app.meeting.utils import RESYNC, is_valid_uuid, live_transcript_hub

logger = get_logger(__name__)

meeting_router = APIRouter(
    prefix="/api/meetings", tags=["Meetings"], dependencies=[Depends(require_user_or_api_key)]
)
webhook_router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])
meeting_ws_router = APIRouter(tags=["WebSocket"])

SESSION_ENDED_MESSAGE = "Your session has ended. Please log in again."


@meeting_router.get(
    "",
    response_model=MeetingListResponse,
    summary="List meetings",
    responses={
        **COMMON_ERROR_RESPONSES,
        200: {"model": MeetingListResponse, "description": "Filtered meeting page"},
        400: {"model": BadRequestResponse, "description": "Invalid join time range"},
    },
)
@limiter.limit("30/minute")
async def list_meetings_endpoint(
    request: Request,
    search: Optional[str] = Query(
        None, max_length=100, description="Search meeting title or recipient email"
    ),
    status: Optional[MeetingStatus] = Query(
        None, description="Filter by meeting pipeline status"
    ),
    platform: Optional[MeetingPlatform] = Query(
        None, description="Filter by meeting platform"
    ),
    join_from: Optional[datetime] = Query(
        None, description="Include joins at or after this ISO 8601 time with timezone"
    ),
    join_until: Optional[datetime] = Query(
        None, description="Include joins before this ISO 8601 time with timezone"
    ),
    sort_by: MeetingSortBy = Query(
        MeetingSortBy.TITLE, description="Field used for sorting"
    ),
    sort_order: SortOrder = Query(
        SortOrder.LATEST, description="Sort as latest, oldest, a_to_z, or z_to_a"
    ),
    limit: int = Query(20, ge=1, le=100, description="Meetings per page"),
    offset: int = Query(0, ge=0, description="Meetings skipped before this page"),
) -> MeetingListResponse:
    """
    List saved meetings with filters and pagination.

    - **search**: optional partial match on title or recipient email
    - **status**: optional, scheduled, joining, in_progress, processing, completed, or failed
    - **platform**: optional, google_meet or teams
    - **join_from**: optional ISO 8601 time with timezone, inclusive scheduled join filter
    - **join_until**: optional ISO 8601 time with timezone, exclusive scheduled join filter
    - **sort_by**: title, status, created_at, or join_at
    - **sort_order**: latest, oldest, a_to_z, or z_to_a, defaults to latest
    - **limit**: 1 to 100 meetings per page, defaults to 20
    - **offset**: number of matching meetings to skip, defaults to 0
    - needs a logged in Bearer token or the **X-API-Key** header
    """
    try:
        if (join_from and join_from.tzinfo is None) or (
            join_until and join_until.tzinfo is None
        ):
            raise BadRequestException("Join time filters must include a timezone")
        if join_from and join_until and join_from >= join_until:
            raise BadRequestException("join_from must be before join_until")
        meetings, total = await list_meetings(
            search,
            status,
            platform,
            join_from,
            join_until,
            sort_by,
            sort_order,
            limit,
            offset,
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
    - needs a logged in Bearer token or the **X-API-Key** header
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
    - needs a logged in Bearer token or the **X-API-Key** header
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
        409: {
            "model": ConflictResponse,
            "description": "Bot is already leaving or has left",
        },
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
    - returns 409 when the bot is already leaving, post processing, or ended
    - needs a logged in Bearer token or the **X-API-Key** header
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
    - needs a logged in Bearer token or the **X-API-Key** header
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


async def send_json(websocket: WebSocket, data: dict) -> bool:
    try:
        await websocket.send_json(data)
        return True
    except Exception:
        return False


async def _close_with(websocket: WebSocket, code: WSCloseCode, message: str) -> None:
    await send_json(websocket, WSFailedMessage(message=message).model_dump())
    try:
        await websocket.close(code=code)
    except Exception:
        pass


async def _receive_token(websocket: WebSocket) -> object:
    try:
        message = await asyncio.wait_for(
            websocket.receive_json(), timeout=settings.LIVE_TRANSCRIPT_AUTH_TIMEOUT_SECONDS
        )
    except (asyncio.TimeoutError, ValueError, KeyError):
        return None
    return message.get("token") if isinstance(message, dict) else None


async def _snapshot_message(meeting_id: str) -> dict:
    return WSSnapshotMessage(data=await get_live_snapshot(meeting_id)).model_dump(mode="json")


async def _stream_events(websocket: WebSocket, meeting_id: str, token: str, queue: asyncio.Queue) -> None:
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=settings.LIVE_TRANSCRIPT_PING_SECONDS)
        except asyncio.TimeoutError:
            if await authenticate_ws(token) is None:
                await _close_with(websocket, WSCloseCode.AUTH_FAILED, SESSION_ENDED_MESSAGE)
                return
            event = WSPingMessage().model_dump()
        if event is RESYNC:
            event = await _snapshot_message(meeting_id)
        if not await send_json(websocket, event):
            return


async def _wait_for_disconnect(websocket: WebSocket) -> None:
    while (await websocket.receive())["type"] != "websocket.disconnect":
        continue


@meeting_ws_router.websocket("/api/ws/meetings/{meeting_id}/transcript")
async def live_transcript_socket(websocket: WebSocket, meeting_id: str) -> None:
    """
    Stream a meeting's transcript live.

    - **meeting_id**: the meeting UUID, passed in the path
    - the first client message must be {"token": "<access token>"}, sent within 10 seconds
    - the server sends snapshot with the full transcript, then utterance for each new or updated line, status when the meeting changes, and ping every 25 seconds
    - an utterance whose utterance_id is already shown replaces that line, a snapshot replaces everything
    - the login is checked again on every ping, so logout or a password change closes the socket
    - close codes are 4001 login missing or ended, 4002 bad meeting_id, 4003 server error, 4004 meeting not found
    """
    await websocket.accept()
    queue: Optional[asyncio.Queue] = None
    try:
        token = await _receive_token(websocket)
        if await authenticate_ws(token) is None:
            await _close_with(websocket, WSCloseCode.AUTH_FAILED, "Please log in to continue")
            return
        if not is_valid_uuid(meeting_id):
            await _close_with(
                websocket, WSCloseCode.INVALID_PARAMS, "Invalid meeting_id format. Expected a valid UUID."
            )
            return
        meeting_id = str(uuid.UUID(meeting_id))
        # Subscribe before the snapshot so a line saved in between is not lost.
        queue = live_transcript_hub.subscribe(meeting_id)
        if not await send_json(websocket, await _snapshot_message(meeting_id)):
            return

        stream = asyncio.create_task(_stream_events(websocket, meeting_id, token, queue))
        watcher = asyncio.create_task(_wait_for_disconnect(websocket))
        await asyncio.wait({stream, watcher}, return_when=asyncio.FIRST_COMPLETED)
        for task in (stream, watcher):
            task.cancel()
        stream_result, _ = await asyncio.gather(stream, watcher, return_exceptions=True)
        if isinstance(stream_result, Exception):
            raise stream_result
    except WebSocketDisconnect:
        logger.info(f"Live transcript client left meeting {meeting_id}")
    except NotFoundException:
        await _close_with(websocket, WSCloseCode.NOT_FOUND, "Meeting not found")
    except Exception as e:
        logger.error(f"Live transcript socket error for meeting {meeting_id}: {e}")
        await _close_with(websocket, WSCloseCode.SERVER_ERROR, "Something went wrong. Please reconnect.")
    finally:
        if queue is not None:
            live_transcript_hub.unsubscribe(meeting_id, queue)
