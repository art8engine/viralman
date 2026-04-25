# Sample runs

Three end-to-end traces showing what `/viral` produces for different intents and modes. These are illustrative — your actual output will vary because the writer + sniffer loop is not deterministic.

---

## Run 1 — growth-story, all platforms

### Input

```
/viral our k8s autoscaler cut our prod cloud bill 47% in three weeks. one of the wins was switching from per-request boto3 sessions to a shared one. happy to share the config diff. --subreddit programming
```

### Plan (printed by the skill)

```
intent: open-source K8s autoscaler, 47% cost reduction, shared boto3 sessions
targets: reddit (r/programming), x, linkedin
mode: growth-story
anchors: 47% cost cut · 3 weeks · per-request → shared boto3 sessions
```

### Draft — Reddit (`r/programming`, 412 words after sniffer pass 1)

```
TITLE: Cut our prod k8s autoscaler bill 47% in 3 weeks — main fix was per-request boto3 sessions
BODY:
Posting because I went looking for war stories on this and didn't find one that named the actual fix, so here's mine.

We were running a custom HPA-on-steroids autoscaler that called AWS APIs (DescribeInstances, DescribeAutoScalingGroups) on every reconcile. ~30 reconciles/sec across the fleet. The autoscaler itself wasn't the problem — the cost was the per-request boto3 client construction. Each reconcile was opening a new TLS connection, paying TCP handshake + TLS handshake + STS GetSessionToken, then closing.

We didn't notice for months because the per-request latency budget had headroom. The cost showed up on the AWS bill as `STS:GetSessionToken` calls and `EC2:DescribeInstances` request count (yes, you pay for these in volume).

The fix was four lines:

```python
# before — every reconcile
def reconcile(...):
    ec2 = boto3.client("ec2", region_name=region)
    ...

# after — module-level shared client
_ec2 = boto3.client("ec2", region_name=region)
def reconcile(...):
    ...
```

The AWS docs literally warn about this. I'd read those docs. I didn't connect them to our autoscaler because the autoscaler "felt like" a system that needed fresh state per reconcile. It doesn't. Boto3 clients are thread-safe and the underlying connection pool is what you actually want.

Other smaller wins that contributed to the 47%:
- Replaced `time.sleep(1)` reconcile loop with a controller-runtime workqueue (~ -8% from fewer redundant calls).
- Cached `DescribeInstances` for 30s where stale data was acceptable (most reconcile decisions tolerate it).
- Set `boto3.client(..., config=Config(retries={"mode": "adaptive"}))` so we stopped hammering the API on transient errors.

Three weeks because I spent the first two convinced the bill was a misconfigured Cost Explorer rule. It wasn't.

Repo with the diff: https://github.com/<org>/<repo>/pull/<n>
```

(Sniffer pass 1: 0 flags. No rewrite needed.)

### Draft — X (3-tweet thread)

```
1/ cut our prod k8s autoscaler aws bill 47% in 3 weeks.

main fix was 4 lines: stop creating a new boto3 client every reconcile.
---
2/ each reconcile was paying TCP handshake + TLS handshake + STS GetSessionToken. ~30 reconciles/sec across the fleet.

bill showed up as `STS:GetSessionToken` volume. months before we connected it.
---
3/ fix:

# before
def reconcile():
    ec2 = boto3.client("ec2")

# after
_ec2 = boto3.client("ec2")
def reconcile():
    ...

aws docs literally warn about this. i'd read those docs.
```

(Sniffer pass 1: 0 flags.)

### Draft — LinkedIn (~1100 chars after sniffer pass 1)

```
We cut our production K8s autoscaler's AWS bill 47% in three weeks. The main fix was four lines.

Each reconcile in our autoscaler was creating a new boto3 client. ~30 reconciles per second across the fleet. Every one was paying a fresh TCP handshake, TLS handshake, and STS GetSessionToken call.

We didn't catch it for months because the per-request latency had headroom. The cost showed up on the AWS bill as STS GetSessionToken volume and EC2 Describe* request count. (Yes, you pay for these in volume.)

The fix was moving the boto3 client construction from per-reconcile to module-level. Boto3 clients are thread-safe; the connection pool is what you actually want anyway.

Other contributors to the 47%: replacing the sleep-based reconcile loop with a workqueue, caching DescribeInstances for 30 seconds where stale was acceptable, and switching to adaptive retry mode.

Three weeks because I spent the first two convinced the bill was a misconfigured Cost Explorer rule.
```

(Sniffer pass 1: 0 flags.)

### Confirm

```
[reddit r/programming] post  edit  regenerate  skip
[x thread]            post  edit  regenerate  skip
[linkedin]            post  edit  regenerate  skip
```

User typed `post all`, publisher ran:

```
[reddit] OK https://www.reddit.com/r/programming/comments/abc123/...
[linkedin] OK https://www.linkedin.com/feed/update/urn:li:share:7188...
[x] OK https://twitter.com/<handle>/status/178000...
```

Audit log entry:

```jsonl
{"ts":"2026-04-25T16:55:11Z","platform":"reddit","mode":"growth-story","subreddit":"programming","url":"https://reddit.com/r/programming/comments/abc123","chars":2087,"flags":[]}
{"ts":"2026-04-25T16:55:14Z","platform":"linkedin","mode":"growth-story","url":"https://www.linkedin.com/feed/update/urn:li:share:7188","chars":1098,"flags":[]}
{"ts":"2026-04-25T16:55:17Z","platform":"x","mode":"growth-story","url":"https://twitter.com/<handle>/status/178000","chars":280,"flags":[]}
```

---

## Run 2 — casual-hype, X only

### Input

```
/viral 3주동안 미친듯 디버깅한 flaky 테스트 원인이 pytest fixture scope 한 줄이었다 --only x --mode casual-hype
```

(Korean intent → English output.)

### Plan

```
intent: 3-week flaky test debug, fix was pytest fixture scope
targets: x
mode: casual-hype
anchors: 3 weeks · scope=function · fixture
```

### Draft — X (1 tweet, 138 chars)

```
three weeks debugging the flakiest test of my life. fix was scope="function". one word. absolute W.
```

(Sniffer pass 1: 0 flags. The em-dash budget for casual-hype is 0; this draft has 0. "absolute W" is one of the allowed casual-hype tokens.)

### Confirm + post

```
[x] post  edit  regenerate
```

User picked `post`. Twitter API not configured, so:

```
[x] DRAFT https://twitter.com/intent/tweet?text=three%20weeks%20debugging... (open in browser to send)
```

Browser opened to the compose URL. User clicked Tweet.

---

## Run 3 — show-and-tell with sniffer rewrite

### Input

```
/viral i just shipped a thing called gnarly that visualizes regex matches on stdin. zero deps, single rust binary --mode show-and-tell --only reddit --subreddit SideProject
```

### Draft — Reddit, sniffer pass 1 (FLAGGED)

```
TITLE: I built a game-changing CLI that revolutionizes how you think about regex
BODY:
In today's fast-paced developer world, regex debugging is essential. I built `gnarly` to leverage the power of streaming stdin and unlock the potential of color-coded capture group visualization.

It's not just a tool — it's a paradigm shift in how you debug logs.

- Streams input
- Colors capture groups
- Single Rust binary

What do you think? Drop a 👇 below.
```

Sniffer flags found:

```
FLAG [banned-phrase]: game-changing
FLAG [banned-phrase]: revolutionize
FLAG [banned-phrase]: in today's X world
FLAG [banned-phrase]: leverage (verb)
FLAG [banned-phrase]: unlock the X
FLAG [banned-pattern]: 'It's not just X — it's Y'
FLAG [banned-phrase]: paradigm shift
FLAG [linkedin-template]: hook + 3 bullets + CTA shape (also flags on Reddit since shape is the issue)
FLAG [no-anchor]: no number, specific name, time anchor, or admission found
```

### Draft — Reddit, sniffer pass 2 (rewritten)

```
TITLE: I built `gnarly` — a CLI that colors which chars in your stdin a regex actually matched
BODY:
Tool's called `gnarly`. Pipe anything to it with a regex and it prints your input back with each char colored by which capture group it landed in (or grey if it didn't match).

```
cat access.log | gnarly '^(\S+) - (\S+) \[([^\]]+)\]'
```

Built it because I kept switching between three half-good tools when debugging logs:
- regex101 — great UX, can't paste 50MB of logs into a webpage
- `grep --color` — fast, only colors the whole match, not capture groups
- python repl — works, I write it from scratch every time

The piece I'm proud of: it streams. You can pipe an unbounded source into it and watch the colors update as bytes come in. Most regex visualizers buffer the whole input first.

Stack: Rust, ~600 lines. Single binary, zero runtime deps.

Repo: https://github.com/<me>/gnarly

Would love to see what regex you're using that breaks it. I've tested on Apache logs and JSON; the corner cases I haven't seen are probably the ones I'll fix this weekend.
```

(Sniffer pass 2: 0 flags. Anchors present: tool name `gnarly`, code example, "600 lines", repo URL, "this weekend".)

### Confirm + post

```
[reddit r/SideProject] post  edit  regenerate
```

User picked `post`. Publisher:

```
[reddit] OK https://www.reddit.com/r/SideProject/comments/xyz789/...
```

---

## What these traces are showing

- The same intent can land cleanly on pass 1 (Run 1) or need a rewrite (Run 3).
- The sniffer doesn't care about the writer's draft length — it cares about the heuristics. Run 3's pass-1 draft was shorter than the rewritten version.
- Korean intent + English output is fine; the writer translates intent into native-feeling English (Run 2).
- API-less posting on X falls back to the intent URL with no UX cliff.

If your runs look meaningfully different from these traces, that's worth knowing — open an issue and paste your draft + flags.
