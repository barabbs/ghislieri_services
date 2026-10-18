"""Outgoing email over SMTP (Gmail with an app password)."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from .settings import Settings

log = logging.getLogger(__name__)

Attachment = tuple[str, bytes, str]  # filename, content, MIME type ("application/pdf")


def _send_sync(settings: Settings, msg: EmailMessage) -> None:
    assert settings.smtp_password is not None
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.login(settings.smtp_user or "", settings.smtp_password.get_secret_value())
        smtp.send_message(msg)


async def send(
    settings: Settings,
    to: list[str],
    subject: str,
    body: str,
    attachments: list[Attachment] = (),  # type: ignore[assignment]
) -> None:
    """Send an email. Raises on failure, so callers can tell the user.

    In dev, mail goes to GS_MAIL_DEV_REDIRECT instead, or is only logged when that is unset.
    Without SMTP credentials mail is only logged.
    """
    to = list(dict.fromkeys(a for a in to if a))
    if not to:
        log.warning("Email %r has no recipients", subject)
        return
    if not settings.is_prod:
        if settings.mail_dev_redirect is None:
            log.info("[dev] Email not sent: to=%s subject=%r attachments=%d", to, subject, len(attachments))
            return
        body = f"[dev, originally to {', '.join(to)}]\n\n{body}"
        to = [settings.mail_dev_redirect]
    if settings.smtp_password is None:
        log.warning("SMTP not configured; email %r to %s not sent", subject, to)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.smtp_user, ", ".join(to), subject
    msg.set_content(body)
    for filename, content, mime in attachments:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
    await asyncio.to_thread(_send_sync, settings, msg)
    log.info("Email %r sent to %d recipients", subject, len(to))
