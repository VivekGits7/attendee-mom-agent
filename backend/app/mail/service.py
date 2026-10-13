from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional

import aiosmtplib

from app.config import settings
from app.error import ExternalServiceException
from app.logger import get_logger

logger = get_logger(__name__)


def is_allowed_recipient(email: Optional[str]) -> bool:
    if not email or "@" not in email:
        return False
    return email.rsplit("@", 1)[1].lower() in settings.ALLOWED_EMAIL_DOMAINS


async def send_email(
    to_email: str, subject: str, text_body: str, html_body: str
) -> None:
    message = EmailMessage()
    message["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USERNAME or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_START_TLS,
            use_tls=settings.SMTP_USE_SSL,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        )
    except (aiosmtplib.SMTPException, OSError) as e:
        logger.error(f"Email to {to_email} failed: {type(e).__name__}")
        raise ExternalServiceException("Could not send the email") from e
    logger.info(f"Minutes email sent to {to_email}")
