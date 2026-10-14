import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.attendee import close_attendee_client
from app.common import (
    HealthCheckResponse,
    HealthData,
    InternalServerErrorResponse,
    RateLimitResponse,
)
from app.config import settings
from app.database import close_db_pool, create_db_pool
from app.error import setup_error_handlers
from app.limiter import limiter
from app.logger import get_logger, setup_logging
from app.meeting import meeting_router, webhook_router
from app.meeting.calendar import run_teams_calendar_sync
from app.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware

load_dotenv()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_pool()
    logger.info("Database pool created")
    calendar_task = None
    if settings.TEAMS_CALENDAR_ENABLED:
        if all((settings.MICROSOFT_TENANT_ID, settings.MICROSOFT_CLIENT_ID, settings.MICROSOFT_CLIENT_SECRET)):
            calendar_task = asyncio.create_task(run_teams_calendar_sync())
            logger.info("Teams calendar watcher started")
        else:
            logger.error("Teams calendar watcher needs Microsoft tenant, client ID, and client secret")
    try:
        yield
    finally:
        if calendar_task:
            calendar_task.cancel()
            try:
                await calendar_task
            except asyncio.CancelledError:
                pass
        await close_attendee_client()
        await close_db_pool()
        logger.info("Database pool closed")


app = FastAPI(
    title=settings.APP_NAME,
    description="Sends a notetaker bot to Meet and Teams, stores the transcript and emails the minutes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.state.limiter = limiter
setup_error_handlers(app)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)

allowed_origins = settings.CORS_ORIGINS if settings.is_production else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meeting_router)
app.include_router(webhook_router)


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    responses={
        200: {"model": HealthCheckResponse, "description": "Service health status"},
        429: {
            "model": RateLimitResponse,
            "description": "Rate limit exceeded for this endpoint",
        },
        500: {
            "model": InternalServerErrorResponse,
            "description": "Unexpected server error",
        },
    },
)
@limiter.limit("60/minute")
async def health_check(request: Request) -> HealthCheckResponse:
    return HealthCheckResponse(
        success=True,
        message="Service is healthy",
        data=HealthData(status="healthy", service=settings.APP_NAME),
    )
