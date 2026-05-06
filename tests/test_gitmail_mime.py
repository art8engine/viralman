"""RFC 5322 / 8058 compliance regression tests for smtp_send.render_preview.

Validates that generated email envelopes conform to:
  - RFC 5322 (Internet Message Format)
  - RFC 2369 (List-Unsubscribe header)
  - RFC 8058 (One-Click Unsubscribe)

Run: .venv/bin/python -m pytest tests/test_gitmail_mime.py -v
"""

from __future__ import annotations

import re
import sys
import urllib.parse
from email import message_from_string
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts" / "lib"))

import smtp_send  # noqa: E402


CREDS = {
    "SMTP_FROM": "me@example.com",
    "SMTP_USER": "me@example.com",
    "SMTP_FROM_NAME": "Sender",
}

UNSUB_BASE = "https://viralman.local"


def _render(**kwargs) -> dict:
    """Call render_preview with defaults, allow overrides."""
    defaults = dict(
        to_addr="alice@example.com",
        subject="Test subject",
        body="Hello, this is a test email body.",
        unsubscribe_base=UNSUB_BASE,
    )
    defaults.update(kwargs)
    return smtp_send.render_preview(CREDS, **defaults)


def _parsed_msg(out: dict):
    """Parse the raw message string and return an email.message.Message object."""
    return message_from_string(out["raw"])


def _extract_message_id(out: dict) -> str:
    """Extract Message-ID value from the headers string."""
    for line in out["headers"].splitlines():
        if line.startswith("Message-ID:"):
            return line.split(":", 1)[1].strip()
    return ""


# ---------------------------------------------------------------------------
# 1. Full message parses without error
# ---------------------------------------------------------------------------

def test_headers_parse_as_valid_email():
    out = _render()
    msg = message_from_string(out["raw"])
    # email.message_from_string never raises; validate we got a real object
    # with expected fields, not a degenerate parse.
    assert msg["From"] is not None, "Parsed message has no From header"
    assert msg["To"] is not None, "Parsed message has no To header"


# ---------------------------------------------------------------------------
# 2. Required headers present
# ---------------------------------------------------------------------------

REQUIRED_HEADERS = [
    "From",
    "To",
    "Subject",
    "Date",
    "Message-ID",
    "MIME-Version",
    "Content-Type",
    "List-Unsubscribe",
    "List-Unsubscribe-Post",
]


@pytest.mark.parametrize("header", REQUIRED_HEADERS)
def test_required_headers_present(header):
    out = _render()
    msg = _parsed_msg(out)
    assert msg[header] is not None, f"Missing required header: {header}"


# ---------------------------------------------------------------------------
# 3. Message-ID is well-formed per RFC 5322
# ---------------------------------------------------------------------------

def test_message_id_is_well_formed():
    out = _render()
    mid = _extract_message_id(out)
    assert re.match(r"^<[^@<>]+@[^@<>]+>$", mid), (
        f"Message-ID does not match <local@domain> shape: {mid!r}"
    )


# ---------------------------------------------------------------------------
# 4. Date header is RFC 5322 parseable
# ---------------------------------------------------------------------------

def test_date_is_rfc5322_parseable():
    out = _render()
    msg = _parsed_msg(out)
    date_str = msg["Date"]
    assert date_str, "Date header is empty"
    dt = parsedate_to_datetime(date_str)
    assert dt is not None, f"Could not parse Date header: {date_str!r}"


# ---------------------------------------------------------------------------
# 5. From uses display name when SMTP_FROM_NAME is set
# ---------------------------------------------------------------------------

def test_from_address_uses_display_name():
    out = _render()
    msg = _parsed_msg(out)
    name, addr = parseaddr(msg["From"])
    assert name == "Sender", f"Expected display name 'Sender', got {name!r}"
    assert addr == "me@example.com", f"Expected address 'me@example.com', got {addr!r}"


# ---------------------------------------------------------------------------
# 6. List-Unsubscribe header is URI form per RFC 2369
# ---------------------------------------------------------------------------

def test_list_unsubscribe_header_is_uri_form():
    out = _render()
    msg = _parsed_msg(out)
    header_val = msg["List-Unsubscribe"]
    assert header_val, "List-Unsubscribe header is missing or empty"

    # Extract angle-bracketed URIs
    uris = re.findall(r"<([^>]+)>", header_val)
    assert uris, f"No angle-bracketed URIs found in List-Unsubscribe: {header_val!r}"

    for uri in uris:
        parsed = urllib.parse.urlparse(uri)
        assert parsed.scheme in ("https", "http", "mailto"), (
            f"List-Unsubscribe URI has unexpected scheme {parsed.scheme!r}: {uri!r}"
        )


# ---------------------------------------------------------------------------
# 7. List-Unsubscribe-Post is exactly the RFC 8058 value
# ---------------------------------------------------------------------------

def test_list_unsubscribe_one_click_compliant():
    out = _render()
    msg = _parsed_msg(out)
    post_val = msg["List-Unsubscribe-Post"]
    assert post_val is not None, "List-Unsubscribe-Post header is missing"
    assert post_val.strip() == "List-Unsubscribe=One-Click", (
        f"List-Unsubscribe-Post value incorrect: {post_val!r}"
    )


# ---------------------------------------------------------------------------
# 8. Unsubscribe token appears in both the header URI and the body
# ---------------------------------------------------------------------------

def test_unsubscribe_token_appears_in_both_header_and_body():
    out = _render()
    token = out["unsubscribe_token"]
    assert token, "unsubscribe_token is empty"

    # Check it's in the List-Unsubscribe header
    assert token in out["headers"], (
        f"Token {token!r} not found in headers"
    )

    # Check it's in the body (the decoded plain-text body)
    assert token in out["body"], (
        f"Token {token!r} not found in body"
    )


# ---------------------------------------------------------------------------
# 9. Body contains human-readable unsubscribe instruction
# ---------------------------------------------------------------------------

def test_body_includes_human_unsubscribe_text():
    out = _render()
    body = out["body"]
    # The footer template is a single short line: "Unsubscribe: <url>"
    assert "unsubscribe" in body.lower(), (
        "Body does not contain any unsubscribe instruction"
    )
    # And the actual unsubscribe URL must be reachable from the body itself,
    # not only the List-Unsubscribe header.
    assert out["unsubscribe_token"] in body, (
        "Body should contain the unsubscribe URL with its token"
    )


# ---------------------------------------------------------------------------
# 10. Empty subject does not break header parsing
# ---------------------------------------------------------------------------

def test_subject_is_not_empty_string_invalid():
    # Passing an empty subject should still produce a parseable message.
    # The Subject header may be empty but must not corrupt other headers.
    out = smtp_send.render_preview(
        CREDS,
        to_addr="alice@example.com",
        subject="",
        body="body text",
        unsubscribe_base=UNSUB_BASE,
    )
    msg = _parsed_msg(out)
    # Other critical headers must still be present even with empty subject
    assert msg["From"] is not None
    assert msg["To"] is not None
    assert msg["Message-ID"] is not None


# ---------------------------------------------------------------------------
# 11. Reply-To appears when set, absent otherwise
# ---------------------------------------------------------------------------

def test_reply_to_appears_when_set():
    out = _render(reply_to="ops@example.com")
    msg = _parsed_msg(out)
    assert msg["Reply-To"] is not None, "Reply-To header missing when reply_to set"
    _, addr = parseaddr(msg["Reply-To"])
    assert addr == "ops@example.com", f"Reply-To address incorrect: {addr!r}"


def test_reply_to_absent_when_not_set():
    out = _render()  # no reply_to
    msg = _parsed_msg(out)
    assert msg["Reply-To"] is None, (
        f"Reply-To should be absent when not set, got: {msg['Reply-To']!r}"
    )


# ---------------------------------------------------------------------------
# 12. build_unsubscribe_url — skip (already covered in test_gitmail_compose.py)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 13. Token is high-entropy and URL-safe
# ---------------------------------------------------------------------------

def test_token_is_high_entropy():
    out = _render()
    token = out["unsubscribe_token"]
    assert len(token) >= 16, (
        f"Token too short ({len(token)} chars), expected >= 16"
    )
    assert re.match(r"^[A-Za-z0-9_-]+$", token), (
        f"Token contains non-URL-safe characters: {token!r}"
    )


# ---------------------------------------------------------------------------
# 14. Multiple renders produce unique tokens and Message-IDs
# ---------------------------------------------------------------------------

def test_multiple_renders_have_unique_tokens_and_ids():
    out1 = _render()
    out2 = _render()

    token1 = out1["unsubscribe_token"]
    token2 = out2["unsubscribe_token"]
    assert token1 != token2, (
        f"Tokens are not unique: both are {token1!r}"
    )

    mid1 = _extract_message_id(out1)
    mid2 = _extract_message_id(out2)
    assert mid1 != mid2, (
        f"Message-IDs are not unique: both are {mid1!r}"
    )


# ---------------------------------------------------------------------------
# 15. Long body with dot-stuffing edge case passes through unchanged
# ---------------------------------------------------------------------------

def test_long_body_has_no_smtp_dot_stuffing_corruption():
    # A line starting with ". " is the classic SMTP dot-stuffing edge case.
    # render_preview should not mangle the body content.
    tricky_body = (
        "Normal first line.\n"
        ". This line starts with a dot followed by a space.\n"
        ".. Double dot line.\n"
        ".\n"
        "Normal last line."
    )
    out = smtp_send.render_preview(
        CREDS,
        to_addr="alice@example.com",
        subject="Dot test",
        body=tricky_body,
        unsubscribe_base=UNSUB_BASE,
    )
    body = out["body"]
    # The dot-prefixed lines must survive unchanged in the decoded body
    assert ". This line starts with a dot followed by a space." in body, (
        "render_preview corrupted a line starting with '. ' (dot-stuffing bug)"
    )
    assert ".. Double dot line." in body, (
        "render_preview corrupted a line starting with '..'"
    )
