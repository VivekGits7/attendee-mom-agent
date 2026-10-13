from types import SimpleNamespace

import pytest

from app.meeting.enums import MeetingPlatform
from app.meeting.utils import (
    build_transcript_text,
    detect_platform,
    format_timestamp,
    render_minutes_email,
)
from app.mom import ActionItem, ActionPriority, Decision, MeetingMinutes


@pytest.mark.parametrize(
    "url, platform",
    [
        ("https://meet.google.com/abc-defg-hij", MeetingPlatform.GOOGLE_MEET),
        (
            "https://teams.microsoft.com/l/meetup-join/19%3ameeting_abc",
            MeetingPlatform.TEAMS,
        ),
        ("https://teams.live.com/meet/9876543210", MeetingPlatform.TEAMS),
        ("https://us05web.zoom.us/j/123", None),
        ("https://meet.google.com.evil.io/abc", None),
        ("not a url", None),
    ],
)
def test_detect_platform(url, platform):
    assert detect_platform(url) == platform


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00"
    assert format_timestamp(1079) == "00:00:01"
    assert format_timestamp(3_725_000) == "01:02:05"


def test_transcript_merges_same_speaker_lines():
    utterances = [
        SimpleNamespace(speaker_name="Vivek", timestamp_ms=0, text="Hi team."),
        SimpleNamespace(speaker_name="Vivek", timestamp_ms=2000, text="Let's start."),
        SimpleNamespace(
            speaker_name="Aniruddha", timestamp_ms=65_000, text="Sounds good."
        ),
    ]

    assert (
        build_transcript_text(utterances)
        == "[00:00:00] Vivek: Hi team. Let's start.\n[00:01:05] Aniruddha: Sounds good."
    )


def test_email_escapes_html_and_lists_action_items():
    minutes = MeetingMinutes(
        summary="Talked about <script>alert(1)</script>",
        key_points=["Point one"],
        decisions=[Decision(decision="Ship Friday", made_by="Group")],
        action_items=[
            ActionItem(
                task="Write tests",
                owner="Vivek",
                due_date="Friday",
                priority=ActionPriority.HIGH,
            )
        ],
        open_questions=[],
        attendees=["Vivek", "Aniruddha"],
    )

    subject, text_body, html_body = render_minutes_email(
        "Sprint <planning>", None, minutes
    )

    assert subject.startswith("MOM: Sprint <planning>")
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body
    assert (
        "Write tests" in html_body
        and "Write tests | Vivek | Friday | high" in text_body
    )
    assert "Ship Friday, by Group" in text_body
