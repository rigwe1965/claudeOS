"""Reminder notification job — runs every 2 minutes via APScheduler.

Queries memory_entries for due reminders (category='reminder',
expires_at <= now, notified_at IS NULL), sends email + .ics calendar invite,
marks notified_at.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("claudeos.notifications.reminder_job")


def _parse_dt(value: str) -> datetime | None:
    """Parse ISO datetime string to UTC datetime."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def run() -> int:
    """Check for due reminders and send email + calendar notifications. Returns count sent."""
    from core.config import get_settings
    from core.database import get_db
    from core.utils import utcnow_str
    from notifications.email import send_reminder

    settings = get_settings()

    # Skip silently if SMTP not configured
    if not all([settings.SMTP_HOST, settings.SMTP_USER, settings.SMTP_PASSWORD, settings.NOTIFY_EMAIL]):
        logger.debug("SMTP not configured — reminder job skipped")
        return 0

    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, namespace, key, value, expires_at
               FROM memory_entries
               WHERE category = 'reminder'
                 AND expires_at IS NOT NULL
                 AND replace(expires_at, 'T', ' ') <= datetime('now')
                 AND notified_at IS NULL""",
        ).fetchall()

    if not rows:
        return 0

    sent = 0
    for row in rows:
        entry_id = row["id"]
        namespace = row["namespace"]
        key = row["key"]
        value = row["value"]
        expires_at = row["expires_at"]

        try:
            # Parse value — scheduling-agent outputs JSON
            try:
                data = json.loads(value)
                action = data.get("action", key)
                confirmation = data.get("confirmation", value)
            except (json.JSONDecodeError, TypeError):
                action = key
                confirmation = str(value)

            # Parse event time for calendar invite
            event_time = _parse_dt(expires_at) if expires_at else None

            subject = f"ClaudeOS Reminder: {action}"
            body = (
                f"ClaudeOS Reminder\n"
                f"{'=' * 40}\n\n"
                f"{confirmation}\n\n"
                f"Namespace: {namespace}\n"
                f"Key: {key}\n"
            )

            send_reminder(
                to=settings.NOTIFY_EMAIL,
                subject=subject,
                body=body,
                smtp_host=settings.SMTP_HOST,
                smtp_port=settings.SMTP_PORT,
                smtp_user=settings.SMTP_USER,
                smtp_password=settings.SMTP_PASSWORD,
                event_time=event_time,
            )

            # Mark as notified
            with get_db() as conn:
                conn.execute(
                    "UPDATE memory_entries SET notified_at = ? WHERE id = ?",
                    (utcnow_str(), entry_id),
                )
            sent += 1
            logger.info("Reminder sent for entry %s (%s) with calendar=%s", entry_id[:8], key, bool(event_time))

        except Exception as e:
            logger.error("Failed to send reminder for entry %s: %s", entry_id[:8], e)

    return sent
