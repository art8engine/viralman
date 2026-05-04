"""LLM provider abstraction for gitmail.

Supports three providers, picked from creds:
  - claude   : ANTHROPIC_API_KEY        (default; "claude max" via API key)
  - openai   : OPENAI_API_KEY
  - gemini   : GEMINI_API_KEY

Two operations:
  - analyse_project(text)        -> {"summary","keywords","topics","value_prop"}
  - compose_email(...)           -> {"subject","body"} per recipient

Everything goes through the stdlib (urllib). Keeps the dep surface tiny.

The agent context never reads creds — only the post_*.py / gitmail.py scripts do.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


# --------------------------------------------------------------------------- #
# Provider routing                                                            #
# --------------------------------------------------------------------------- #


PROVIDER_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gpt": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
}

DEFAULT_MODELS = {
    "claude": "claude-opus-4-7",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}


def _resolve_provider(creds: Dict[str, str], requested: Optional[str] = None) -> str:
    if requested:
        canon = requested.lower()
        if canon in ("claude", "anthropic"):
            return "claude"
        if canon in ("openai", "gpt"):
            return "openai"
        if canon in ("gemini", "google"):
            return "gemini"
    for prov, key in [("claude", "ANTHROPIC_API_KEY"),
                       ("openai", "OPENAI_API_KEY"),
                       ("gemini", "GEMINI_API_KEY")]:
        if creds.get(key):
            return prov
    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "or GEMINI_API_KEY via scripts/save_creds.py."
    )


# --------------------------------------------------------------------------- #
# HTTP helper with retry                                                      #
# --------------------------------------------------------------------------- #


def _post_json(
    url: str,
    *,
    headers: Dict[str, str],
    payload: dict,
    timeout: int = 60,
    max_retries: int = 2,
) -> dict:
    body = json.dumps(payload).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, data=body, method="POST")
        for k, v in headers.items():
            req.add_header(k, v)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = (e.read() or b"").decode("utf-8", errors="replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries:
                time.sleep(2 ** attempt)
                last_err = RuntimeError(f"{e.code}: {err_body[:300]}")
                continue
            raise RuntimeError(f"LLM HTTP {e.code}: {err_body[:500]}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                last_err = e
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("LLM call failed without error")


# --------------------------------------------------------------------------- #
# Per-provider call                                                           #
# --------------------------------------------------------------------------- #


def _call_claude(api_key: str, model: str, system: str, user: str,
                  max_tokens: int = 1500) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    res = _post_json(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        payload=payload,
    )
    parts = res.get("content") or []
    out = []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == "text":
            out.append(p.get("text", ""))
    return "".join(out).strip()


def _call_openai(api_key: str, model: str, system: str, user: str,
                  max_tokens: int = 1500) -> str:
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    res = _post_json(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        payload=payload,
    )
    return (res.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


def _call_gemini(api_key: str, model: str, system: str, user: str,
                  max_tokens: int = 1500) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    res = _post_json(url, headers={}, payload=payload)
    cands = res.get("candidates") or []
    if not cands:
        return ""
    parts = (cands[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def call_llm(
    creds: Dict[str, str],
    *,
    system: str,
    user: str,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 1500,
) -> str:
    prov = _resolve_provider(creds, provider)
    key = creds.get(PROVIDER_KEYS[prov]) or os.environ.get(PROVIDER_KEYS[prov])
    if not key:
        raise RuntimeError(f"missing API key for provider={prov}")
    use_model = model or creds.get("VIRALMAN_LLM_MODEL") or DEFAULT_MODELS[prov]
    if prov == "claude":
        return _call_claude(key, use_model, system, user, max_tokens)
    if prov == "openai":
        return _call_openai(key, use_model, system, user, max_tokens)
    if prov == "gemini":
        return _call_gemini(key, use_model, system, user, max_tokens)
    raise RuntimeError(f"unknown provider {prov}")


# --------------------------------------------------------------------------- #
# JSON-extraction helper                                                      #
# --------------------------------------------------------------------------- #


def _extract_json(text: str) -> dict:
    """Find the first JSON object in `text`. Tolerant to fenced blocks."""
    if not text:
        return {}
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


# --------------------------------------------------------------------------- #
# High-level operations                                                       #
# --------------------------------------------------------------------------- #


_ANALYSE_SYS = (
    "You are an open-source project analyst. Given a short description, return "
    "compact JSON with the project's tech stack and likely GitHub topics. Be "
    "concrete and cite only what's plausibly in the description."
)

_ANALYSE_USER_TMPL = """Project description:
\"\"\"
{description}
\"\"\"

Return ONLY JSON of the form:
{{
  "summary": "<one-sentence summary>",
  "keywords": ["<5-10 specific tech terms>"],
  "topics": ["<3-7 likely github topic slugs>"],
  "value_prop": "<one short sentence on what this project gives a developer>"
}}"""


def analyse_project_llm(creds: Dict[str, str], description: str,
                        *, provider: Optional[str] = None) -> Dict[str, object]:
    raw = call_llm(
        creds,
        system=_ANALYSE_SYS,
        user=_ANALYSE_USER_TMPL.format(description=description.strip()),
        provider=provider,
        max_tokens=600,
    )
    data = _extract_json(raw) or {}
    data.setdefault("summary", "")
    data.setdefault("keywords", [])
    data.setdefault("topics", [])
    data.setdefault("value_prop", "")
    if not isinstance(data["keywords"], list):
        data["keywords"] = []
    if not isinstance(data["topics"], list):
        data["topics"] = []
    return data


_EMAIL_SYS = (
    "You write outreach emails for an open-source maintainer reaching out to a "
    "developer who starred a related project. Keep it short, concrete, and "
    "human. NO marketing slop. NO 'I hope this finds you well'. NO em-dash "
    "floods. Mention the recipient's starred repo to show this is not blast "
    "spam. End with a low-pressure CTA — repo link OR a one-question reply."
)

_EMAIL_USER_TMPL = """My project: {project_name}
What it does: {project_pitch}
Repo URL: {project_url}

Recipient handle: @{login}
A repo they starred that is similar to mine: {starred_repo}

Write the email. Output ONLY JSON:
{{
  "subject": "<<= 60 chars, no clickbait, no emoji>",
  "body": "<plaintext, 90-160 words, addressed to @{login}, mentions {starred_repo} once, ends with CTA>"
}}"""


def compose_email(
    creds: Dict[str, str],
    *,
    project_name: str,
    project_pitch: str,
    project_url: str,
    login: str,
    starred_repo: str,
    provider: Optional[str] = None,
) -> Dict[str, str]:
    raw = call_llm(
        creds,
        system=_EMAIL_SYS,
        user=_EMAIL_USER_TMPL.format(
            project_name=project_name,
            project_pitch=project_pitch,
            project_url=project_url or "(none)",
            login=login,
            starred_repo=starred_repo,
        ),
        provider=provider,
        max_tokens=700,
    )
    data = _extract_json(raw)
    subject = (data.get("subject") or "").strip().strip('"')
    body = (data.get("body") or "").strip()
    if not subject:
        subject = f"Quick note about {project_name}"
    if not body:
        body = raw.strip()
    return {"subject": subject[:160], "body": body}


# --------------------------------------------------------------------------- #
# CLI smoke test                                                              #
# --------------------------------------------------------------------------- #


def _main() -> int:
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyse")
    a.add_argument("description")
    a.add_argument("--provider", default=None)
    e = sub.add_parser("email")
    e.add_argument("--project", required=True)
    e.add_argument("--pitch", required=True)
    e.add_argument("--url", default="")
    e.add_argument("--login", required=True)
    e.add_argument("--starred", required=True)
    e.add_argument("--provider", default=None)
    args = p.parse_args()

    sys.path.insert(0, str(Path(__file__).parent))
    from creds import load as load_creds
    creds = load_creds()

    if args.cmd == "analyse":
        print(json.dumps(analyse_project_llm(creds, args.description,
                                             provider=args.provider), indent=2))
        return 0
    if args.cmd == "email":
        print(json.dumps(
            compose_email(creds,
                          project_name=args.project,
                          project_pitch=args.pitch,
                          project_url=args.url,
                          login=args.login,
                          starred_repo=args.starred,
                          provider=args.provider),
            indent=2,
        ))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
