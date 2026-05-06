"""SMTP sender for gitmail.

Uses ~/.viralman/.env values:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
  SMTP_SECURITY      ("starttls" default | "ssl" | "none")
  SMTP_RATE_PER_MIN  (default 30)

Always appends an unsubscribe footer + List-Unsubscribe header. Supports a
dry-run mode that returns the constructed MIME without hitting the network —
the dashboard uses this for the preview pane.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
import urllib.parse
import uuid
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional


UNSUBSCRIBE_FOOTER_TMPL = (
    "\n\nUnsubscribe: {unsubscribe_url}\n"
)


class SmtpError(Exception):
    pass


def _require(creds: Dict[str, str], keys: Iterable[str]) -> Dict[str, str]:
    missing = [k for k in keys if not creds.get(k)]
    if missing:
        raise SmtpError(f"missing SMTP creds: {missing}")
    return {k: creds[k] for k in keys}


def _connect(creds: Dict[str, str]) -> smtplib.SMTP:
    host = creds["SMTP_HOST"]
    port = int(creds.get("SMTP_PORT") or 587)
    security = (creds.get("SMTP_SECURITY") or "starttls").lower()
    timeout = int(creds.get("SMTP_TIMEOUT") or 30)

    if security == "ssl":
        ctx = ssl.create_default_context()
        s: smtplib.SMTP = smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout)
    else:
        s = smtplib.SMTP(host, port, timeout=timeout)
        s.ehlo()
        if security == "starttls":
            ctx = ssl.create_default_context()
            s.starttls(context=ctx)
            s.ehlo()
    user = creds.get("SMTP_USER")
    pw = creds.get("SMTP_PASSWORD")
    if user and pw:
        s.login(user, pw)
    return s


def _build_message(
    *,
    sender: str,
    sender_name: Optional[str],
    to_addr: str,
    subject: str,
    body: str,
    unsubscribe_url: str,
    reply_to: Optional[str] = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name or "", sender))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Date"] = format_datetime(datetime.now(timezone.utc))
    msg["Message-ID"] = make_msgid(domain=sender.split("@")[-1] if "@" in sender else "viralman")
    msg["List-Unsubscribe"] = f"<{unsubscribe_url}>, <mailto:{sender}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    if reply_to:
        msg["Reply-To"] = reply_to

    full_body = body.rstrip() + UNSUBSCRIBE_FOOTER_TMPL.format(
        unsubscribe_url=unsubscribe_url
    )
    msg.set_content(full_body)
    return msg


def build_unsubscribe_url(base: str, token: str) -> str:
    base = base.rstrip("/")
    return f"{base}/u/{urllib.parse.quote(token, safe='')}"


def render_preview(
    creds: Dict[str, str],
    *,
    to_addr: str,
    subject: str,
    body: str,
    unsubscribe_base: str = "https://viralman.local",
    reply_to: Optional[str] = None,
) -> Dict[str, str]:
    """Build the MIME envelope without sending. For the dashboard preview."""
    sender = creds.get("SMTP_FROM") or creds.get("SMTP_USER") or "viralman@localhost"
    sender_name = creds.get("SMTP_FROM_NAME")
    token = uuid.uuid4().hex
    msg = _build_message(
        sender=sender,
        sender_name=sender_name,
        to_addr=to_addr,
        subject=subject,
        body=body,
        unsubscribe_url=build_unsubscribe_url(unsubscribe_base, token),
        reply_to=reply_to,
    )
    return {
        "from": str(msg["From"]),
        "to": str(msg["To"]),
        "subject": str(msg["Subject"]),
        "headers": "\n".join(f"{k}: {v}" for k, v in msg.items()),
        "body": msg.get_content(),
        "raw": msg.as_string(),
        "unsubscribe_token": token,
    }


def send_one(
    smtp: smtplib.SMTP,
    creds: Dict[str, str],
    *,
    to_addr: str,
    subject: str,
    body: str,
    unsubscribe_base: str,
    reply_to: Optional[str] = None,
) -> Dict[str, str]:
    sender = creds.get("SMTP_FROM") or creds["SMTP_USER"]
    sender_name = creds.get("SMTP_FROM_NAME")
    token = uuid.uuid4().hex
    msg = _build_message(
        sender=sender,
        sender_name=sender_name,
        to_addr=to_addr,
        subject=subject,
        body=body,
        unsubscribe_url=build_unsubscribe_url(unsubscribe_base, token),
        reply_to=reply_to,
    )
    smtp.send_message(msg)
    return {
        "to": to_addr,
        "subject": subject,
        "message_id": str(msg["Message-ID"]),
        "unsubscribe_token": token,
    }


class RateLimiter:
    """Simple per-minute rate limiter."""

    def __init__(self, per_minute: int):
        self.per_minute = max(1, per_minute)
        self._times: list[float] = []

    def wait(self) -> None:
        now = time.monotonic()
        cutoff = now - 60.0
        self._times = [t for t in self._times if t >= cutoff]
        if len(self._times) >= self.per_minute:
            sleep_for = 60.0 - (now - self._times[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
        self._times.append(time.monotonic())


def open_session(creds: Dict[str, str]) -> tuple[smtplib.SMTP, RateLimiter]:
    _require(creds, ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"])
    s = _connect(creds)
    per_min = int(creds.get("SMTP_RATE_PER_MIN") or 30)
    return s, RateLimiter(per_min)
