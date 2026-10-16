import asyncio
import html
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Tuple
from urllib.parse import urlparse

from app.config import settings
from app.meeting.enums import MeetingPlatform
from app.mom import MeetingMinutes

TEAMS_HOSTS = ("teams.microsoft.com", "teams.live.com")

RESYNC = object()


class LiveTranscriptHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, dict[asyncio.Queue, asyncio.AbstractEventLoop]] = defaultdict(dict)

    def subscribe(self, meeting_id: str | uuid.UUID) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=settings.LIVE_TRANSCRIPT_QUEUE_SIZE)
        self._subscribers[str(meeting_id)][queue] = asyncio.get_running_loop()
        return queue

    def unsubscribe(self, meeting_id: str | uuid.UUID, queue: asyncio.Queue) -> None:
        key = str(meeting_id)
        self._subscribers.get(key, {}).pop(queue, None)
        if not self._subscribers.get(key):
            self._subscribers.pop(key, None)

    def has_subscribers(self, meeting_id: str | uuid.UUID) -> bool:
        return bool(self._subscribers.get(str(meeting_id)))

    def publish(self, meeting_id: str | uuid.UUID, message: Any) -> None:
        for queue, loop in list(self._subscribers.get(str(meeting_id), {}).items()):
            loop.call_soon_threadsafe(_offer, queue, message)

    def resync(self, meeting_id: str | uuid.UUID) -> None:
        self.publish(meeting_id, RESYNC)


# A socket that falls this far behind drops its backlog and reloads the whole transcript instead.
def _offer(queue: asyncio.Queue, message: Any) -> None:
    try:
        queue.put_nowait(message)
    except asyncio.QueueFull:
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(RESYNC)


live_transcript_hub = LiveTranscriptHub()


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


def _email_text(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")


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

    outcome_rows = (
        "".join(
            "<tr><td style='padding:15px 0;border-bottom:1px solid #e5ebea;vertical-align:top'>"
            "<table role='presentation' cellpadding='0' cellspacing='0' width='100%'><tr>"
            f"<td style='width:28px;color:#2d81ff;font-size:12px;font-weight:700;vertical-align:top'>{index:02d}</td>"
            "<td style='color:#253238;font-size:15px;line-height:1.5'>"
            f"<strong style='font-weight:600'>{_email_text(outcome.item)}</strong>"
            + (
                f"<div style='margin-top:5px;color:#728187;font-size:12px'>Owner: {_email_text(outcome.owner)}</div>"
                if outcome.owner
                else ""
            )
            + (
                f"<div style='margin-top:3px;color:#728187;font-size:12px'>Due: {_email_text(outcome.due_date)}</div>"
                if outcome.due_date
                else ""
            )
            + "</td></tr></table></td></tr>"
            for index, outcome in enumerate(minutes.outcomes, start=1)
        )
        or "<tr><td style='padding:14px 0;color:#728187;font-size:14px'>No outcomes recorded.</td></tr>"
    )
    question_rows = (
        "".join(
            "<tr><td style='padding:11px 0;border-bottom:1px solid #e5ebea;color:#344249;font-size:14px;line-height:1.5'>"
            f"<span style='color:#2d81ff;font-weight:700;margin-right:10px'>{index:02d}</span>{_email_text(question)}"
            "</td></tr>"
            for index, question in enumerate(minutes.open_questions, start=1)
        )
        or "<tr><td style='padding:12px 0;color:#728187;font-size:14px'>No open questions.</td></tr>"
    )

    html_body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f3f0;font-family:Arial,Helvetica,sans-serif;color:#253238">
  <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f2f3f0"><tr><td align="center" style="padding:28px 12px">
    <table role="presentation" cellpadding="0" cellspacing="0" width="640" style="width:100%;max-width:640px;background:#ffffff;border:1px solid #dce3e2">
      <tr><td style="padding:26px 34px;background:#080808;color:#ffffff">
        <span style="display:inline-block;width:10px;height:10px;margin-right:10px;background:#2d81ff;vertical-align:middle"></span>
        <span style="font-size:13px;font-weight:700;letter-spacing:2px;vertical-align:middle">ATTENDEE <span style="color:#8b9ba5;font-weight:400">/ STUDIO</span></span>
      </td></tr>
      <tr><td style="padding:36px 34px 18px">
        <p style="margin:0 0 12px;color:#2d81ff;font-size:11px;font-weight:700;letter-spacing:2px">MEETING NOTES / {meeting_date.upper()}</p>
        <h1 style="margin:0;color:#17262e;font-size:30px;line-height:1.15;font-weight:600;letter-spacing:-1px">{_email_text(title)}</h1>
        <p style="margin:13px 0 0;color:#728187;font-size:14px;line-height:1.5">The conversation, decisions, and next steps in one place.</p>
      </td></tr>
      <tr><td style="padding:18px 34px 0">
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#edf4ff;border-left:3px solid #2d81ff"><tr><td style="padding:21px 23px">
          <p style="margin:0 0 8px;color:#2d66a4;font-size:11px;font-weight:700;letter-spacing:1.5px">01 / SUMMARY</p>
          <p style="margin:0;color:#253238;font-size:16px;line-height:1.6">{_email_text(minutes.summary)}</p>
        </td></tr></table>
      </td></tr>
      <tr><td style="padding:32px 34px 0">
        <h2 style="margin:0 0 9px;color:#17262e;font-size:21px;font-weight:600;letter-spacing:-.5px">Outcomes<span style="color:#2d81ff">.</span></h2>
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%">{outcome_rows}</table>
      </td></tr>
      <tr><td style="padding:32px 34px 40px">
        <h2 style="margin:0 0 9px;color:#17262e;font-size:21px;font-weight:600;letter-spacing:-.5px">Open questions<span style="color:#2d81ff">.</span></h2>
        <table role="presentation" cellpadding="0" cellspacing="0" width="100%">{question_rows}</table>
      </td></tr>
      <tr><td style="padding:21px 34px;background:#080808;color:#9da6aa;font-size:12px;line-height:1.5">
        <strong style="color:#ffffff;letter-spacing:1px">ATTENDEE / STUDIO</strong><br>Meetings, made useful.
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""

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
