"""Send the digest by e-mail (SMTP). The SMTP connection is injectable."""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from typing import Callable, Optional


def build_message(subject: str, text: str, html: str, sender: str, recipients: list[str]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def _default_factory(host: str, port: int):  # pragma: no cover - needs a mail server
    if port == 465:
        return smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30)
    return smtplib.SMTP(host, port, timeout=30)


def send(
    msg: EmailMessage,
    host: str,
    port: int = 587,
    user: Optional[str] = None,
    password: Optional[str] = None,
    smtp_factory: Callable = _default_factory,
) -> None:
    """Raises on any failure, so the caller never marks alerts as sent by mistake."""
    with smtp_factory(host, port) as smtp:
        if port != 465:
            smtp.starttls(context=ssl.create_default_context())
        if user:
            smtp.login(user, password or "")
        smtp.send_message(msg)
