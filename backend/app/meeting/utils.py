import html
import uuid
from datetime import datetime, timezone
from typing import Iterable, Optional, Tuple
from urllib.parse import urlparse

from app.meeting.enums import MeetingPlatform
from app.mom import MeetingMinutes

TEAMS_HOSTS = ("teams.microsoft.com", "teams.live.com")


def detect_platform(meeting_url: str) -> Optional[MeetingPlatform]:
    host = (urlparse(meeting_url).hostname or "").lower()
    if host == "meet.google.com":
        return MeetingPlatform.GOOGLE_MEET
    if host in TEAMS_HOSTS or host.endswith(".teams.microsoft.com"):
        return MeetingPlatform.TEAMS
    return None


def is_valid_uuid(value: Optional[str]) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, TypeError):
        return False


def format_timestamp(timestamp_ms: int) -> str:
    total_seconds = max(timestamp_ms, 0) // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def build_transcript_text(utterances: Iterable) -> str:
    utterances = list(utterances)
    # Attendee timestamps are Unix time in ms, so each line is labelled with time since the first one.
    start_ms = min((utterance.timestamp_ms for utterance in utterances), default=0)
    lines: list[str] = []
    last_speaker: Optional[str] = None
    for utterance in utterances:
        if utterance.speaker_name == last_speaker and lines:
            lines[-1] += f" {utterance.text}"
            continue
        lines.append(
            f"[{format_timestamp(utterance.timestamp_ms - start_ms)}] {utterance.speaker_name}: {utterance.text}"
        )
        last_speaker = utterance.speaker_name
    return "\n".join(lines)


def _html_list(items: list[str]) -> str:
    if not items:
        return "<p>Nothing recorded.</p>"
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def render_minutes_email(
    title: str, ended_at: Optional[datetime], minutes: MeetingMinutes
) -> Tuple[str, str, str]:
    meeting_date = (ended_at or datetime.now(timezone.utc)).strftime("%d %b %Y")
    subject = f"MOM: {title} ({meeting_date})"
    outcomes = [
        f"{outcome.item}"
        f"{' — ' + outcome.owner if outcome.owner else ''}"
        f"{' (Due: ' + outcome.due_date + ')' if outcome.due_date else ''}"
        for outcome in minutes.outcomes
    ]

    html_body = (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
        f"<h2>{html.escape(title)}</h2><p><b>Date:</b> {meeting_date}</p>"
        f"<h3>Summary</h3><p>{html.escape(minutes.summary)}</p>"
        f"<h3>Outcomes</h3>{_html_list(outcomes)}"
        f"<h3>Open questions</h3>{_html_list(minutes.open_questions)}"
        "</div>"
    )

    text_lines = [
        title,
        f"Date: {meeting_date}",
        "",
        "SUMMARY",
        minutes.summary,
        "",
        "OUTCOMES",
        *[f"- {outcome}" for outcome in outcomes],
        "",
        "OPEN QUESTIONS",
        *[f"- {q}" for q in minutes.open_questions],
    ]
    return subject, "\n".join(text_lines), html_body
