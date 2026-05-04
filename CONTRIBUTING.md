# Contributing to viralman

Thanks for considering a contribution. viralman is a small, opinionated tool — that means we lean toward fewer features that work cleanly over many features that don't. PRs that delete code are extra welcome.

## Quickstart

```bash
git clone https://github.com/art8engine/viralman
cd viralman
python3 -m venv .venv
.venv/bin/pip install flask ruff
.venv/bin/pip install -e .
```

Run the dashboard locally:

```bash
.venv/bin/python bin/viralman --no-browser
```

Run tests:

```bash
.venv/bin/python -m unittest tests.test_gitmail_compose -v
.venv/bin/python tests/test_ai_tells.py
```

Run the linter / formatter:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

CI runs all of the above on every push/PR against Python 3.11, 3.12, and 3.13.

## What we like in PRs

- **Small scope.** One reason per PR. Easier to review, easier to revert.
- **A test that fails before your fix and passes after.** For new features, a focused test that demonstrates the behavior.
- **No new dependencies** unless there's no reasonable stdlib path. We try to keep `pip install viralman` light — Flask is the only mandatory dep.
- **No new "AI-feeling" copy** in user-facing strings, README, or docs. The whole point of this tool is dodging that voice; the README and templates should walk the talk.
- **Secrets stay out of the LLM context.** If your PR adds a new credential type, follow the existing `read -s → save_creds.py --stdin` pattern.

## Adding a new platform

To add a fourth post target (Mastodon, Bluesky, etc.):

1. Add a `scripts/post_<platform>.py` mirroring `post_reddit.py` — read body from stdin, print URL on success.
2. Add a credential setup skill at `skills/viralman-login-<platform>/SKILL.md`.
3. Add it to the dashboard: a new template + JS file under `dashboard/`, plus a tab in `templates/base.html`.
4. Wire `dashboard/api.py` and `dashboard/oauth.py` if the platform supports OAuth.
5. Update the AI-tell sniffer with platform-specific rules in `voice/platform-norms.md`.

## Voice mode contributions

`voice/modes/` has four modes. New modes are welcome but should:

- Be backed by 5+ real (anonymized) reference posts in `voice/reference-corpus/`.
- Include explicit anti-pattern examples — the kind of sentences this mode should *not* produce.
- Pass the existing AI-tell sniffer self-test without weakening any rule.

## Reporting bugs / requesting features

Use the GitHub issue templates in `.github/ISSUE_TEMPLATE/`. For security issues, see `SECURITY.md` — please do not open public issues for those.

## Code of Conduct

This project adopts the Contributor Covenant 2.1. See `CODE_OF_CONDUCT.md`.

## License

By contributing, you agree your contributions are licensed under the MIT License.
