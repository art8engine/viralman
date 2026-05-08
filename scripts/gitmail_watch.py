#!/usr/bin/env python3
"""Live progress watcher for gitmail send-from-recipients runs.

Usage:
  ./scripts/gitmail_watch.py /tmp/gitmail_send_viralman.json
  ./scripts/gitmail_watch.py --auto                # pick newest /tmp/gitmail_send_*.json
  ./scripts/gitmail_watch.py --auto --once         # print one line and exit (statusLine)

Renders a single-line live progress display:
  [sending] 412/1266 ok | 8 fail | 0 skip | ETA ~28m | last: ok -> user@example.com

Auto-exits when a send_done or done event is seen, or on Ctrl-C.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
from pathlib import Path

EVENT_RE = re.compile(r'\{[^{}]*"event":[^{}]*\}')


def _find_auto_path() -> Path | None:
    candidates = sorted(glob.glob("/tmp/gitmail_send_*.json"),
                          key=os.path.getmtime)
    return Path(candidates[-1]) if candidates else None


def _parse_events(text: str):
    for m in EVENT_RE.finditer(text):
        try:
            yield json.loads(m.group(0))
        except json.JSONDecodeError:
            continue


def _fmt_eta(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "-"
    if seconds < 60:
        return f"~{seconds}s"
    if seconds < 3600:
        return f"~{seconds // 60}m{seconds % 60}s"
    return f"~{seconds // 3600}h{(seconds % 3600) // 60}m"


def _render(state: dict) -> str:
    return (f"[{state['phase']}] {state['sent']}/{state['target']} ok | "
            f"{state['failed']} fail | {state['skipped']} skip | "
            f"ETA {_fmt_eta(state.get('eta_s'))} | last: {state['last']}")


def _apply(state: dict, ev: dict) -> bool:
    """Mutate state from one event. Return True if this is a terminal event."""
    t = ev.get("event")
    if t == "recipients_loaded":
        state["phase"] = "compose"
        state["target"] = ev.get("count", 0)
    elif t == "compose_done":
        state["phase"] = "send_ready"
    elif t == "send_start":
        state["phase"] = "sending"
        state["target"] = ev.get("count", state["target"])
    elif t == "send_ok":
        state["sent"] = ev.get("sent", state["sent"] + 1)
        state["last"] = f"ok -> {ev.get('to','')}"
    elif t == "send_fail":
        state["failed"] = ev.get("failed", state["failed"] + 1)
        state["last"] = f"fail -> {ev.get('to','')}"
    elif t == "send_skip":
        state["skipped"] += 1
    elif t == "send_aborted":
        state["phase"] = "aborted"
        err = ev.get("first_blocking_error", "")[:60]
        state["last"] = f"aborted: {err}"
    elif t == "send_done":
        state["phase"] = "done"
        state["last"] = (f"sent={ev.get('sent')} "
                          f"failed={ev.get('failed')} "
                          f"unprocessed={ev.get('unprocessed', 0)}")
        return True
    elif t == "done":
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", help="Path to events JSON file")
    ap.add_argument("--auto", action="store_true",
                     help="Pick the newest /tmp/gitmail_send_*.json")
    ap.add_argument("--interval", type=float, default=1.0,
                     help="Refresh interval seconds (default 1.0)")
    ap.add_argument("--once", action="store_true",
                     help="Print one snapshot line and exit (for statusLine)")
    args = ap.parse_args()

    if args.path:
        path = Path(args.path)
    elif args.auto:
        found = _find_auto_path()
        if not found:
            print("no /tmp/gitmail_send_*.json found", file=sys.stderr)
            return 2
        path = found
    else:
        ap.print_usage()
        return 2

    state = {"phase": "-", "sent": 0, "failed": 0,
             "skipped": 0, "target": 0, "last": "-"}
    sent_history: list[tuple[float, int]] = []
    done = False

    if not args.once:
        print(f"watching: {path}")

    try:
        while not done:
            if not path.exists():
                if args.once:
                    print(_render(state))
                    return 0
                sys.stdout.write(f"\r(waiting for {path}...)\033[K")
                sys.stdout.flush()
                time.sleep(args.interval)
                continue

            text = path.read_text(encoding="utf-8", errors="replace")
            for ev in _parse_events(text):
                if _apply(state, ev):
                    done = True

            # ETA: rate over last 30s
            now = time.time()
            sent_history.append((now, state["sent"]))
            sent_history = [(ts, s) for ts, s in sent_history
                              if ts > now - 30]
            if len(sent_history) >= 2 and state["target"]:
                dt = sent_history[-1][0] - sent_history[0][0]
                ds = sent_history[-1][1] - sent_history[0][1]
                if dt > 0 and ds > 0:
                    rate = ds / dt
                    remaining = state["target"] - state["sent"]
                    state["eta_s"] = int(remaining / rate)

            line = _render(state)
            if args.once:
                print(line)
                return 0

            sys.stdout.write(f"\r{line}\033[K")
            sys.stdout.flush()

            if not done:
                time.sleep(args.interval)

        sys.stdout.write("\n")
        return 0
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
