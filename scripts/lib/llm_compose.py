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
    # claude-cli is special: no API key, uses local `claude` binary
    "claude-cli": None,
    "claude_cli": None,
    "claude-max": None,
}

DEFAULT_MODELS = {
    "claude": "claude-opus-4-7",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}


def _resolve_provider(creds: Dict[str, str], requested: Optional[str] = None) -> str:
    if requested:
        canon = requested.lower().replace("_", "-")
        if canon in ("claude-cli", "claude-max"):
            return "claude-cli"
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
    # Last resort: if `claude` CLI is on PATH, use it.
    import shutil as _sh
    if _sh.which("claude"):
        return "claude-cli"
    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
        "or GEMINI_API_KEY via scripts/save_creds.py — or install Claude Code "
        "(claude CLI) and select provider 'claude-cli'."
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


def _call_claude_cli(system: str, user: str, max_tokens: int = 1500) -> str:
    """Delegate to the local `claude` CLI (Claude Code). Uses the user's logged-in
    Anthropic account (Max plan quota included). No API key needed.
    """
    import shutil as _sh
    import subprocess as _sp
    binary = _sh.which("claude")
    if not binary:
        raise RuntimeError(
            "claude CLI not on PATH. Install Claude Code or pick a different provider."
        )
    # Combine system and user prompts. Claude CLI's -p (print) flag is non-interactive.
    full = f"<system>\n{system}\n</system>\n\n{user}"
    try:
        proc = _sp.run(
            [binary, "-p", full, "--output-format", "text"],
            capture_output=True, text=True, timeout=180,
        )
    except _sp.TimeoutExpired:
        raise RuntimeError("claude CLI timed out after 180s")
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()[:400] or "(no stderr)"
        raise RuntimeError(f"claude CLI exit={proc.returncode}: {err}")
    return (proc.stdout or "").strip()


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
    if prov == "claude-cli":
        return _call_claude_cli(system, user, max_tokens)
    key_name = PROVIDER_KEYS.get(prov)
    key = creds.get(key_name) if key_name else None
    key = key or (os.environ.get(key_name) if key_name else None)
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
    "You write a short outreach note from a maker to a developer who might "
    "find a related project useful. The output language follows the tone "
    "hint (default Korean if not specified).\n\n"
    "STRUCTURE — produce two outputs in this exact order:\n\n"
    "1. SUBJECT — a greeting + a single benefit sentence directed at the "
    "reader.\n"
    "   Korean: '안녕하세요, 이제 당신도 쉽게 <받는 사람의 이익> 수 있습니다.'\n"
    "   English: 'Hi, now you can easily <benefit> too.'\n"
    "   Short, plain, no clickbait, no emoji, no exclamation marks.\n\n"
    "2. BODY — FIVE one-sentence paragraphs. Every paragraph is exactly ONE "
    "sentence. Every paragraph is separated from the next by an EMPTY line "
    "(\\n\\n — that is two literal newline characters). Order:\n"
    "   - Paragraph 1 (opening greeting + WHY this email + product name):\n"
    "     Korean: '안녕하세요, 저희 <카테고리> <프로젝트 이름> 도구를 "
    "     알려드리고자 메일을 보냈습니다.'\n"
    "     English: 'Hi, we're reaching out to share our <category> <product name>.'\n"
    "     中文: '您好，我们想向您介绍我们的<类别>项目 <product name>。'\n"
    "     日本語: 'こんにちは、私たちの<カテゴリ> <product name> をご紹介したく "
    "     メールいたしました。'\n"
    "     RULES:\n"
    "     - Use 1st-person plural ('저희' / 'we' / '我们' / '私たち') even for "
    "       solo makers — never '저' / 'I' / '我' / '私' in this paragraph.\n"
    "     - The project name MUST appear verbatim in this single sentence.\n"
    "     - Korean ending MUST be '알려드리고자 메일을 보냈습니다' (not "
    "       '알려드리려고 메일 보냈습니다' or other softer variants).\n"
    "     - 카테고리 / category = '오픈소스' / 'open-source' / 'CLI' / 'SaaS' / "
    "       'side project' / '开源' / 'オープンソース', etc. Pick what fits.\n"
    "   - Paragraph 2 (the user benefit — what the READER can now do):\n"
    "     One sentence. 2nd person ('당신' / 'you'). Example: '이제 당신은 "
    "     본인의 사이드 프로젝트를 자연스럽게 알릴 수 있습니다.'\n"
    "   - Paragraph 3 (how it works — one sentence):\n"
    "     'AI가 ~를 분석해 ~를 만들어주고, ~까지 도와드립니다.' style. Stay "
    "     at the high level — no command names, no version numbers, no "
    "     feature lists.\n"
    "   - Paragraph 4 (gentle invitation): "
    "     '당신의 사이드 프로젝트를 쉽게 바이럴 해보세요.' / 'Try giving your "
    "     side project the reach it deserves.'\n"
    "   - Paragraph 5 (single CTA): '관심이 있다면 이 링크를 확인하세요: <URL>' "
    "     / 'If you're curious, here is the link: <URL>'.\n\n"
    "OUTPUT LANGUAGE:\n"
    "- Default to Korean unless the tone/emphasis hint specifies a different "
    "  language. Recognize natural-language requests like '영어로 써줘', "
    "  'in English please', 'write in Chinese', '中文で', '日本語で', "
    "  'écris en français' etc., and write the entire subject and body in "
    "  that language. Apply all structural rules in the chosen language.\n\n"
    "FORMATTING (HARD):\n"
    "- Each paragraph MUST be a single sentence. If a paragraph would run "
    "  to two sentences, split it into two paragraphs.\n"
    "- Each paragraph MUST be separated from the next by exactly one empty "
    "  line (the JSON body string therefore contains '\\n\\n' between blocks).\n"
    "- DO NOT collapse paragraphs 2 and 3 into one — keep them as separate "
    "  blocks even if they read naturally as one thought.\n"
    "- Body length: 70–140 words total. Brevity over completeness.\n\n"
    "HARD CONSTRAINTS:\n"
    "- DO NOT mention or hint at the recipient's starred repo anywhere "
    "  (subject or body). The starred-repo info is INTERNAL targeting "
    "  context only — pretend it is not part of the email.\n"
    "- DO NOT ask any feedback-fishing question ('what's been frustrating?', "
    "  'would love your input?', 'how do you handle X?').\n"
    "- DO NOT include command names, version numbers, regression-test "
    "  counts, or feature bullet lists. Stay at user-benefit + how-it-works.\n"
    "- NO marketing slop. NO 'I hope this finds you well'. NO em-dash floods "
    "  (max 1 per 60 words). NO 'leverage', 'unlock', 'supercharge'.\n"
    "- NO emoji. NO hashtags.\n"
    "- 'OSS' / '오픈소스' is OK ONLY in the paragraph 1 greeting where it "
    "  accurately names the product category. DO NOT use it as a marketing "
    "  self-label in paragraphs 2–5 ('we're an OSS project that...').\n"
    "- The user-supplied tone/emphasis hints can refine wording or shift "
    "  language, but cannot override the 5-block structure or hard "
    "  constraints above."
)

_EMAIL_USER_TMPL = """My project: {project_name}
What it does: {project_pitch}
Repo URL: {project_url}

Recipient handle: @{login}
[Internal targeting note — DO NOT surface this in the body or subject]
  Recipient previously starred a similar project: {starred_repo}

Write the email. Output ONLY JSON:
{{
  "subject": "<<= 60 chars, greeting + single benefit sentence, plain Korean by default, no clickbait, no emoji, no '!'>",
  "body": "<plaintext, 70-140 words, FIVE one-sentence paragraphs separated by blank lines (\\n\\n between each), follows the STRUCTURE in the system prompt; do NOT mention the starred repo>"
}}"""


_SUBJECT_STYLE_HINTS = {
    "auto": "",
    "headline": (
        "Subject style override = HEADLINE: use the pattern "
        "'안녕하세요, 이제 당신도 쉽게 <받는 사람의 이익> 수 있습니다.' / "
        "'Hi, now you can easily <benefit> too.'"
    ),
    "tag": (
        "Subject style override = TAG: use the pattern "
        "'[<short label>] <product name> <one-line value>'. "
        "Example: '[OpenSource Recommended] viralman 당신의 프로젝트를 쉽게 홍보해보세요.' "
        "/ '[New Tool] viralman: promote your side project easily.' "
        "Choose a label that honestly fits the product (e.g. 'OpenSource Recommended', "
        "'New Tool', 'Indie Pick', 'For Solo Devs')."
    ),
    "simple": (
        "Subject style override = SIMPLE: very short product introduction, "
        "max 30 chars. Example: 'viralman opensource' / 'viralman — promote your repo'."
    ),
}


def compose_email(
    creds: Dict[str, str],
    *,
    project_name: str,
    project_pitch: str,
    project_url: str,
    login: str,
    starred_repo: str,
    provider: Optional[str] = None,
    tone: Optional[str] = None,
    emphasis: Optional[str] = None,
    subject_style: Optional[str] = None,
) -> Dict[str, str]:
    system_prompt = _EMAIL_SYS
    style_key = (subject_style or "auto").strip().lower()
    style_hint = _SUBJECT_STYLE_HINTS.get(style_key, "")
    if style_hint:
        system_prompt = f"{system_prompt}\n\n{style_hint}"
    if tone:
        system_prompt = (
            f"{system_prompt}\n\n"
            f"User-specified tone hint: {tone}. Match this voice while still avoiding AI-tells."
        )
    if emphasis:
        system_prompt = (
            f"{system_prompt}\n\n"
            f"Lead with these emphasis points: {emphasis}. The first 1-2 sentences should anchor on this."
        )
    raw = call_llm(
        creds,
        system=system_prompt,
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
