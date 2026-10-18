"""SMTP transport security regressions; no external mail server required."""
import smtplib
import ssl
from unittest.mock import MagicMock, call

import pytest

from core import notifications


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
