import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlparse

import httpx

from app.config import settings
from app.error import ExternalServiceException
GRAPH_URL = "https://graph.microsoft.com/v1.0"
TEAMS_LINK = re.compile(r"https://(?:[a-z0-9-]+\.)?teams\.microsoft\.com/l/meetup-join/[^\s\"'<>]+", re.I)


def _is_teams_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host in {"teams.microsoft.com", "teams.live.com"} or host.endswith(".teams.microsoft.com")
    )


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    title: str
    meeting_url: str
    start_at: datetime
    end_at: datetime
    organizer_email: str | None
    is_recurring: bool = False


def _utc_date(value: dict) -> datetime:
    parsed = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _meeting_url(event: dict) -> str | None:
    url = (event.get("onlineMeeting") or {}).get("joinUrl")
    if url and _is_teams_url(url):
        return url
    body = html.unescape((event.get("body") or {}).get("content") or "")
    match = TEAMS_LINK.search(body)
    if match:
        url = match.group(0).rstrip(".,;)")
        if _is_teams_url(url):
            return url
    return None


def parse_calendar_event(event: dict) -> CalendarEvent | None:
    if event.get("isCancelled") or event.get("isAllDay"):
        return None
    if (event.get("responseStatus") or {}).get("response") == "declined":
        return None
    url = _meeting_url(event)
    if not url:
        return None
    start_at, end_at = _utc_date(event["start"]), _utc_date(event["end"])
    if end_at <= datetime.now(timezone.utc):
        return None
    organizer = (event.get("organizer") or {}).get("emailAddress") or {}
    return CalendarEvent(
        event_id=event["id"],
        title=(event.get("subject") or "Teams meeting")[:255],
        meeting_url=url,
        start_at=start_at,
        end_at=end_at,
        organizer_email=organizer.get("address"),
        is_recurring=bool(event.get("seriesMasterId")) or event.get("type") in {"occurrence", "exception"},
    )


async def list_calendar_events() -> tuple[list[CalendarEvent], set[str], datetime, datetime]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=4)
    window_end = now + timedelta(days=settings.TEAMS_CALENDAR_LOOKAHEAD_DAYS)
    mailbox = quote(str(settings.TEAMS_CALENDAR_MAILBOX), safe="")
    token_url = f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            auth = await client.post(
                token_url,
                data={
                    "client_id": settings.MICROSOFT_CLIENT_ID,
                    "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            if auth.status_code != 200:
                raise ExternalServiceException(f"Microsoft sign-in failed with HTTP {auth.status_code}")
            token = auth.json()["access_token"]
            url = f"{GRAPH_URL}/users/{mailbox}/calendar/calendarView"
            params = {
                "startDateTime": window_start.isoformat(),
                "endDateTime": window_end.isoformat(),
                "$select": "id,subject,start,end,isCancelled,isAllDay,responseStatus,organizer,onlineMeeting,body,seriesMasterId,type",
                "$top": "100",
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.timezone="UTC", IdType="ImmutableId"',
            }
            events: list[CalendarEvent] = []
            ids: set[str] = set()
            while url:
                response = await client.get(url, params=params, headers=headers)
                if response.status_code != 200:
                    raise ExternalServiceException(f"Microsoft calendar read failed with HTTP {response.status_code}")
                page = response.json()
                for raw in page.get("value", []):
                    parsed = parse_calendar_event(raw)
                    if parsed:
                        events.append(parsed)
                        ids.add(parsed.event_id)
                url = page.get("@odata.nextLink")
                if url and not url.startswith(f"{GRAPH_URL}/"):
                    raise ExternalServiceException("Microsoft calendar returned an invalid page URL")
                params = None
            return events, ids, window_start, window_end
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ExternalServiceException("Could not read the Microsoft calendar") from exc
