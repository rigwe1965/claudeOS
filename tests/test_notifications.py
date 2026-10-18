"""SMTP and calendar security regressions; no external mail server required."""
import smtplib
import ssl
from datetime import datetime, timezone
from email import message_from_string
from unittest.mock import MagicMock, call

import pytest

from core import notifications
from notifications import email as reminder_email


@pytest.fixture(params=[465, 587, 2525])
def smtp_transport(request, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", str(request.param))
    monkeypatch.setenv("SMTP_USER", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test-password")
    monkeypatch.setenv("SMTP_FROM", "notifications@example.com")
    transport = MagicMock()
    smtp_ssl = MagicMock()
    smtp = MagicMock()
    transport.__enter__.return_value = transport
    factory = smtp_ssl if request.param == 465 else smtp
    factory.return_value = transport
    monkeypatch.setattr(notifications.smtplib, "SMTP_SSL", smtp_ssl)
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp)
    return request.param, factory, transport


def test_send_email_verifies_tls_before_sending(smtp_transport):
    port, factory, transport = smtp_transport

    assert notifications.send_email("recipient@example.com", "Subject", "<p>Private</p>")

    if port == 465:
        context = factory.call_args.kwargs["context"]
        transport.starttls.assert_not_called()
        factory.assert_called_once_with("smtp.example.com", port, timeout=10, context=context)
    else:
        context = transport.starttls.call_args.kwargs["context"]
        factory.assert_called_once_with("smtp.example.com", port, timeout=10)
        assert transport.method_calls[:2] == [call.ehlo(), call.starttls(context=context)]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    transport.login.assert_called_once_with("sender@example.com", "test-password")
    transport.sendmail.assert_called_once()
    sender, recipients, message = transport.sendmail.call_args.args
    assert transport.method_calls[-2:] == [
        call.login("sender@example.com", "test-password"),
        call.sendmail(sender, recipients, message),
    ]
    assert sender == "notifications@example.com"
    assert recipients == ["recipient@example.com"]
    assert "Subject: Subject" in message


@pytest.mark.parametrize("error", [
    ssl.SSLCertVerificationError("untrusted certificate"),
    ssl.SSLCertVerificationError("hostname mismatch"),
    smtplib.SMTPNotSupportedError("TLS unavailable"),
])
def test_tls_failure_prevents_credentials_and_message(smtp_transport, error, caplog):
    port, factory, transport = smtp_transport
    if port == 465:
        factory.side_effect = error
    else:
        transport.starttls.side_effect = error

    assert notifications.send_email("recipient@example.com", "Subject", "Private") is False

    transport.login.assert_not_called()
    transport.sendmail.assert_not_called()
    assert "Email send failed" in caplog.text


@pytest.fixture()
def reminder_transport(monkeypatch):
    transport = MagicMock()
    transport.__enter__.return_value = transport
    factory = MagicMock(return_value=transport)
    monkeypatch.setattr(reminder_email.smtplib, "SMTP", factory)
    return factory, transport


@pytest.mark.parametrize("event_time", [None, datetime(2026, 10, 18, 12, tzinfo=timezone.utc)])
def test_reminder_verifies_tls_before_sending(reminder_transport, event_time):
    factory, transport = reminder_transport

    reminder_email.send_reminder(
        to="recipient@example.com",
        subject="ClaudeOS Reminder: Meeting",
        body="Private reminder",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_password="test-password",
        event_time=event_time,
    )

    factory.assert_called_once_with("smtp.example.com", 587, timeout=15)
    transport.starttls.assert_called_once()
    context = transport.starttls.call_args.kwargs["context"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    transport.login.assert_called_once_with("sender@example.com", "test-password")
    transport.sendmail.assert_called_once()
    sender, recipient, message = transport.sendmail.call_args.args
    assert transport.method_calls == [
        call.ehlo(),
        call.starttls(context=context),
        call.login("sender@example.com", "test-password"),
        call.sendmail(sender, recipient, message),
    ]
    assert sender == "sender@example.com"
    assert recipient == "recipient@example.com"
    msg = message_from_string(message)
    assert msg["Subject"] == "ClaudeOS Reminder: Meeting"
    parts = msg.get_payload()
    assert parts[0].get_payload(decode=True).decode("utf-8") == "Private reminder"
    assert len(parts) == (2 if event_time else 1)
    if event_time:
        assert parts[1].get_content_type() == "text/calendar"
        assert "DTSTART:20261018T120000Z" in parts[1].get_payload(decode=True).decode("utf-8")


@pytest.mark.parametrize("error", [
    ssl.SSLCertVerificationError("untrusted certificate"),
    ssl.SSLCertVerificationError("hostname mismatch"),
    smtplib.SMTPNotSupportedError("TLS unavailable"),
])
def test_reminder_tls_failure_prevents_credentials_and_message(reminder_transport, error):
    _, transport = reminder_transport
    transport.starttls.side_effect = error

    with pytest.raises(type(error)):
        reminder_email.send_reminder(
            to="recipient@example.com",
            subject="Reminder",
            body="Private reminder",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="sender@example.com",
            smtp_password="test-password",
        )

    transport.login.assert_not_called()
    transport.sendmail.assert_not_called()


@pytest.mark.parametrize("newline", ["\r\n", "\n", "\r"])
def test_reminder_calendar_contains_untrusted_text(reminder_transport, newline):
    _, transport = reminder_transport
    # Non-ASCII subjects survive email header encoding even with newlines.
    title = f"Réunion{newline}ATTENDEE:mailto:injected@example.com{newline}END:VEVENT"
    body = f"Notes{newline}BEGIN:VEVENT{newline}SUMMARY:Injected"
    reminder_email.send_reminder(
        to="recipient@example.com",
        subject=f"ClaudeOS Reminder: {title}",
        body=body,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_password="test-password",
        event_time=datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
    )

    message = message_from_string(transport.sendmail.call_args.args[2])
    attachment = message.get_payload()[1]
    assert attachment.get_content_type() == "text/calendar"
    calendar = attachment.get_payload(decode=True).decode("utf-8")
    lines = calendar.replace("\r\n ", "").split("\r\n")
    assert [line.split(":", 1)[0] for line in lines] == [
        "BEGIN", "VERSION", "PRODID", "METHOD", "BEGIN", "UID", "DTSTAMP",
        "DTSTART", "DTEND", "SUMMARY", "DESCRIPTION", "STATUS", "BEGIN",
        "TRIGGER", "ACTION", "DESCRIPTION", "END", "END", "END", "",
    ]
    assert lines[9] == r"SUMMARY:Réunion\nATTENDEE:mailto:injected@example.com\nEND:VEVENT"
    assert lines[10] == r"DESCRIPTION:Notes\nBEGIN:VEVENT\nSUMMARY:Injected"
    assert lines[15] == r"DESCRIPTION:Réunion\nATTENDEE:mailto:injected@example.com\nEND:VEVENT"
    assert [line for line in lines if line.startswith(("BEGIN:", "END:"))] == [
        "BEGIN:VCALENDAR", "BEGIN:VEVENT", "BEGIN:VALARM",
        "END:VALARM", "END:VEVENT", "END:VCALENDAR",
    ]


def test_calendar_escapes_text_delimiters_and_literal_backslashes():
    calendar = reminder_email._build_ics(
        r"Review\notes, phase; two: details",
        "Literal \\n, comma; semicolon\r\nNew line",
        datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
    )
    lines = calendar.replace("\r\n ", "").split("\r\n")
    assert r"SUMMARY:Review\\notes\, phase\; two: details" in lines
    assert r"DESCRIPTION:Review\\notes\, phase\; two: details" in lines
    assert r"DESCRIPTION:Literal \\n\, comma\; semicolon\nNew line" in lines
    assert "DTSTART:20261018T120000Z" in lines
    assert "DTEND:20261018T123000Z" in lines


@pytest.mark.parametrize("text", ["", "a" * 200, "a" * 66 + "🙂ü漢" * 50])
def test_calendar_folds_lines_without_splitting_utf8(text):
    calendar = reminder_email._build_ics(
        text, text, datetime(2026, 10, 18, 12, tzinfo=timezone.utc),
    )
    for line in calendar.encode("utf-8").split(b"\r\n"):
        assert len(line) <= 75
        line.decode("utf-8")
    unfolded = calendar.replace("\r\n ", "")
    assert f"SUMMARY:{text}\r\n" in unfolded
    assert unfolded.count(f"DESCRIPTION:{text}\r\n") == 2
