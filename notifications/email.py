"""SMTP email sender for ClaudeOS notifications."""
from __future__ import annotations

import logging
import smtplib
import uuid
from datetime import datetime, timezone, timedelta
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

logger = logging.getLogger("claudeos.notifications.email")


def _build_ics(summary: str, description: str, dtstart: datetime) -> str:
    """Build an iCalendar (.ics) string for a 30-minute event."""
    dtend = dtstart + timedelta(minutes=30)
    fmt = "%Y%m%dT%H%M%SZ"
    now = datetime.now(timezone.utc)
    uid = f"{uuid.uuid4()}@claudeos"
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//ClaudeOS//Reminder//EN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now.strftime(fmt)}\r\n"
        f"DTSTART:{dtstart.strftime(fmt)}\r\n"
        f"DTEND:{dtend.strftime(fmt)}\r\n"
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{description.replace(chr(10), '\\n')}\r\n"
        "STATUS:CONFIRMED\r\n"
        "BEGIN:VALARM\r\n"
        "TRIGGER:-PT10M\r\n"
        "ACTION:DISPLAY\r\n"
        f"DESCRIPTION:{summary}\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


def send_reminder(
    to: str,
    subject: str,
    body: str,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_password: str,
    event_time: datetime | None = None,
) -> None:
    """Send a reminder email with optional .ics calendar attachment."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attach .ics if event_time provided
    if event_time:
        ics_content = _build_ics(
            summary=subject.replace("ClaudeOS Reminder: ", ""),
            description=body,
            dtstart=event_time,
        )
        ics_part = MIMEBase("text", "calendar", method="REQUEST", name="reminder.ics")
        ics_part.set_payload(ics_content.encode("utf-8"))
        encoders.encode_base64(ics_part)
        ics_part.add_header("Content-Disposition", "attachment", filename="reminder.ics")
        msg.attach(ics_part)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to, msg.as_string())

    logger.info("Reminder email sent to %s: %s (calendar=%s)", to, subject, bool(event_time))
