#!/usr/bin/env python3
"""Post to LinkedIn via the UGC Posts API.

Reads body from stdin, posts as the authenticated member, prints the post URL.

Usage:
  ./scripts/post_linkedin.py --body -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from creds import load as load_creds, require, read_body_from_stdin_or_arg, CredsError  # noqa: E402


API_ROOT = "https://api.linkedin.com/v2"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--body", default="-")
    p.add_argument("--visibility", default="PUBLIC", choices=["PUBLIC", "CONNECTIONS"])
    args = p.parse_args()

    try:
        creds = load_creds()
        c = require(creds, ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_URN"], "linkedin")
        body = read_body_from_stdin_or_arg(args.body)
    except CredsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    if len(body) > 3000:
        print(f"ERROR: body is {len(body)} chars, LinkedIn cap is 3000", file=sys.stderr)
        return 2

    try:
        import requests  # type: ignore
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {c['LINKEDIN_ACCESS_TOKEN']}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    payload = {
        "author": c["LINKEDIN_PERSON_URN"],
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": body},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": args.visibility,
        },
    }

    try:
        r = requests.post(
            f"{API_ROOT}/ugcPosts",
            headers=headers,
            data=json.dumps(payload),
            timeout=30,
        )
    except Exception as e:
        print(f"ERROR: linkedin request failed: {e}", file=sys.stderr)
        return 1

    if r.status_code not in (200, 201):
        print(f"ERROR: linkedin {r.status_code}: {r.text}", file=sys.stderr)
        return 1

    urn = r.headers.get("x-restli-id") or r.json().get("id", "")
    if urn:
        share_id = urn.split(":")[-1]
        url = f"https://www.linkedin.com/feed/update/{urn}"
        print(url)
    else:
        print("(posted, but no URN returned)", file=sys.stderr)
        print("https://www.linkedin.com/feed/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
