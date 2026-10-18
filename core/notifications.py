"""Email notification service — stdlib smtplib only, no extra packages.

Config via .env:
    SMTP_HOST      — e.g. smtp.gmail.com
    SMTP_PORT      — e.g. 587 (STARTTLS) or 465 (SSL)
    SMTP_USER      — sender email address
    SMTP_PASSWORD  — app password or SMTP password
    SMTP_FROM      — display From (defaults to SMTP_USER)

Silent fail when SMTP not configured — log warning, continue.
"""
from __future__ import annotations

import html as _html

import logging
import os
import smtplib
import ssl
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("claudeos.notifications")

def _smtp_config() -> tuple[str, int, str, str, str]:
    """Read SMTP config from env at call time — safe even if dotenv loads after import."""
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587") or "587")
    user = os.environ.get("SMTP_USER", "")
    pwd  = os.environ.get("SMTP_PASSWORD", "")
    frm  = os.environ.get("SMTP_FROM", user)
    return host, port, user, pwd, frm


def _is_configured() -> bool:
    h, _, u, p, _ = _smtp_config()
    return bool(h and u and p)


def send_email(to: str, subject: str, body_html: str) -> bool:
    """Send HTML email. Returns True on success, False on failure.
    Never raises — all errors are logged as warnings."""
    host, port, user, pwd, frm = _smtp_config()
    if not (host and user and pwd):
        logger.debug("SMTP not configured — skipping notification to %s", to)
        return False
    if not to or "@" not in to:
        logger.debug("Invalid recipient email: %s", to)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = frm
        msg["To"]      = to
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        context = ssl.create_default_context()
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as smtp:
                smtp.login(user, pwd)
                smtp.sendmail(frm, [to], msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.login(user, pwd)
                smtp.sendmail(frm, [to], msg.as_string())

        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception as e:
        logger.warning("Email send failed to %s: %s", to, e)
        return False


def send_async(to: str, subject: str, body_html: str) -> None:
    """Fire-and-forget email in a daemon thread. Never blocks caller."""
    t = threading.Thread(
        target=send_email, args=(to, subject, body_html), daemon=True
    )
    t.start()


# ── Email templates ───────────────────────────────────────────────────────────

def _base_template(title: str, body: str, cta_label: str = "", cta_url: str = "") -> str:
    cta = (
        f'<p style="margin-top:24px;">'
        f'<a href="{cta_url}" style="background:#407E3C;color:#fff;padding:10px 20px;'
        f'border-radius:6px;text-decoration:none;font-weight:600;">{cta_label}</a></p>'
    ) if cta_label and cta_url else ""
    return f"""
<html><body style="font-family:Poppins,Arial,sans-serif;background:#f4f4f4;padding:20px;">
<div style="max-width:520px;margin:auto;background:#fff;border-radius:10px;
            border:1px solid #e5e7eb;overflow:hidden;">
  <div style="background:#407E3C;padding:20px 24px;">
    <div style="font-size:1.2rem;font-weight:800;color:#fff;letter-spacing:2px;">
      CLAUDE<span style="color:#7DBF7E;">OS</span>
    </div>
    <div style="font-size:0.7rem;color:#c8e6c9;letter-spacing:1px;margin-top:2px;">
      AI OPERATING SYSTEM
    </div>
  </div>
  <div style="padding:24px;">
    <h2 style="margin:0 0 12px;color:#1a1a1a;font-size:1.1rem;">{title}</h2>
    <div style="color:#374151;line-height:1.6;font-size:0.92rem;">{body}</div>
    {cta}
  </div>
  <div style="padding:12px 24px;background:#f9fafb;border-top:1px solid #e5e7eb;
              font-size:0.75rem;color:#9ca3af;">
    This is an automated notification from ClaudeOS. Do not reply to this email.
  </div>
</div>
</body></html>"""


def notify_ticket_created(
    assignee_email: str,
    ticket_id: str,
    title: str,
    creator: str,
    namespace: str,
    priority: int,
    dashboard_url: str = "http://localhost:8501",
) -> None:
    """Notify assignee when they are assigned to a new ticket."""
    priority_labels = {1: "P1 — Critical", 2: "P2 — High", 3: "P3 — Normal", 4: "P4 — Low"}
    subject_title = " ".join(str(title).split())  # no CR/LF in headers
    title, creator, namespace = (_html.escape(str(x)) for x in (title, creator, namespace))
    body = (
        f"<p>A ticket has been assigned to you in the <strong>{namespace}</strong> workspace.</p>"
        f"<table style='border-collapse:collapse;width:100%;font-size:0.9rem;'>"
        f"<tr><td style='padding:6px 0;color:#6b7280;width:110px;'>Ticket</td>"
        f"<td style='padding:6px 0;font-weight:600;'>{title}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Created by</td>"
        f"<td style='padding:6px 0;'>{creator}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Priority</td>"
        f"<td style='padding:6px 0;'>{priority_labels.get(priority, str(priority))}</td></tr>"
        f"<tr><td style='padding:6px 0;color:#6b7280;'>Workspace</td>"
        f"<td style='padding:6px 0;'>{namespace}</td></tr>"
        f"</table>"
    )
    send_async(
        to=assignee_email,
        subject=f"[ClaudeOS] Ticket assigned: {subject_title}",
        body_html=_base_template(
            title="You've been assigned a ticket",
            body=body,
            cta_label="View Ticket",
            cta_url=f"{dashboard_url}?page=Tickets",
        ),
    )


def notify_ticket_resolved(
    creator_email: str,
    ticket_id: str,
    title: str,
    resolved_by: str,
    resolution: str,
    dashboard_url: str = "http://localhost:8501",
) -> None:
    """Notify ticket creator when their ticket is completed/closed."""
    subject_title = " ".join(str(title).split())
    title, resolved_by = _html.escape(str(title)), _html.escape(str(resolved_by))
    resolution = _html.escape(str(resolution)) if resolution else resolution
    res_html = (
        f"<p style='background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;"
        f"padding:10px 14px;font-style:italic;color:#166534;margin-top:12px;'>"
        f"{resolution}</p>"
    ) if resolution else ""
    body = (
        f"<p>Your ticket has been resolved by <strong>{resolved_by}</strong>.</p>"
        f"<p style='font-weight:600;color:#1a1a1a;'>{title}</p>"
        f"{res_html}"
    )
    send_async(
        to=creator_email,
        subject=f"[ClaudeOS] Ticket resolved: {subject_title}",
        body_html=_base_template(
            title="Your ticket has been resolved",
            body=body,
            cta_label="View Ticket",
            cta_url=f"{dashboard_url}?page=Tickets",
        ),
    )


def send_test_email(to: str) -> bool:
    """Send a test email — used by admin settings panel."""
    return send_email(
        to=to,
        subject="[ClaudeOS] Test email — notifications working",
        body_html=_base_template(
            title="Test notification",
            body="<p>Email notifications from ClaudeOS are configured correctly. ✅</p>",
        ),
    )
