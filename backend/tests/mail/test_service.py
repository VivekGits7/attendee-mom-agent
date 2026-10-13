import aiosmtplib
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.error import ExternalServiceException
from app.mail import is_allowed_recipient, send_email
from app.mail import service as mail_service


def test_configured_fallback_can_be_outside_recipient_domains():
    config = Settings(
        SMTP_FROM_EMAIL="mom@tcgdigital.com",
        ALLOWED_EMAIL_DOMAINS=["tcgdigital.com"],
        DEFAULT_MOM_EMAIL="fallback@gmail.com",
    )
    assert config.DEFAULT_MOM_EMAIL == "fallback@gmail.com"

    with pytest.raises(ValidationError, match="SMTP_FROM_EMAIL must be on one of"):
        Settings(
            SMTP_FROM_EMAIL="mom@gmail.com",
            ALLOWED_EMAIL_DOMAINS=["tcgdigital.com"],
            DEFAULT_MOM_EMAIL="fallback@gmail.com",
        )

    with pytest.raises(ValidationError):
        Settings(
            SMTP_FROM_EMAIL="mom@tcgdigital.com",
            ALLOWED_EMAIL_DOMAINS=["tcgdigital.com"],
            DEFAULT_MOM_EMAIL="not-an-email",
        )


@pytest.mark.parametrize(
    "email, allowed",
    [
        ("vivek@tcg.com", True),
        ("Vivek@TCG.COM", True),
        ("vivek@gmail.com", False),
        ("vivek@tcg.com.evil.io", False),
        ("not-an-email", False),
        (None, False),
        ("", False),
    ],
)
def test_is_allowed_recipient(email, allowed):
    assert is_allowed_recipient(email) is allowed


async def test_send_email_builds_message_from_verified_sender(monkeypatch):
    sent = {}

    async def fake_send(message, **kwargs):
        sent["message"] = message
        sent["kwargs"] = kwargs

    monkeypatch.setattr(mail_service.aiosmtplib, "send", fake_send)
    await send_email("vivek@tcg.com", "MOM: Sprint", "plain", "<p>html</p>")

    assert sent["message"]["To"] == "vivek@tcg.com"
    assert "mom@tcg.com" in sent["message"]["From"]
    assert sent["message"]["Subject"] == "MOM: Sprint"


async def test_send_email_failure_raises_502(monkeypatch):
    async def failing_send(message, **kwargs):
        raise aiosmtplib.SMTPException("relay denied")

    monkeypatch.setattr(mail_service.aiosmtplib, "send", failing_send)
    with pytest.raises(ExternalServiceException):
        await send_email("vivek@tcg.com", "subject", "plain", "<p>html</p>")
