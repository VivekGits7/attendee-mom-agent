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
    lines: list[str] = []
    last_speaker: Optional[str] = None
    for utterance in utterances:
        if utterance.speaker_name == last_speaker and lines:
            lines[-1] += f" {utterance.text}"
            continue
        lines.append(
            f"[{format_timestamp(utterance.timestamp_ms)}] {utterance.speaker_name}: {utterance.text}"
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

    action_rows = "".join(
        f"<tr><td>{html.escape(a.task)}</td><td>{html.escape(a.owner)}</td>"
        f"<td>{html.escape(a.due_date)}</td><td>{a.priority.value}</td></tr>"
        for a in minutes.action_items
    )
    actions_html = (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
        "<tr><th>Task</th><th>Owner</th><th>Due</th><th>Priority</th></tr>"
        f"{action_rows}</table>"
        if minutes.action_items
        else "<p>No action items.</p>"
    )
    decisions = [f"{d.decision}, by {d.made_by}" for d in minutes.decisions]

    html_body = (
        "<div style='font-family:Arial,sans-serif;font-size:14px;color:#222'>"
        f"<h2>{html.escape(title)}</h2><p><b>Date:</b> {meeting_date}</p>"
        f"<p><b>Attendees:</b> {html.escape(', '.join(minutes.attendees))}</p>"
        f"<h3>Summary</h3><p>{html.escape(minutes.summary)}</p>"
        f"<h3>Action items</h3>{actions_html}"
        f"<h3>Decisions</h3>{_html_list(decisions)}"
        f"<h3>Key points</h3>{_html_list(minutes.key_points)}"
        f"<h3>Open questions</h3>{_html_list(minutes.open_questions)}"
        "</div>"
    )

    text_lines = [
        title,
        f"Date: {meeting_date}",
        f"Attendees: {', '.join(minutes.attendees)}",
        "",
        "SUMMARY",
        minutes.summary,
        "",
        "ACTION ITEMS",
        *[
            f"- {a.task} | {a.owner} | {a.due_date} | {a.priority.value}"
            for a in minutes.action_items
        ],
        "",
        "DECISIONS",
        *[f"- {d}" for d in decisions],
        "",
        "KEY POINTS",
        *[f"- {p}" for p in minutes.key_points],
        "",
        "OPEN QUESTIONS",
        *[f"- {q}" for q in minutes.open_questions],
    ]
    return subject, "\n".join(text_lines), html_body
