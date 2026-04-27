---
name: viralman-login-linkedin
description: Walk the user through registering a LinkedIn app, completing OAuth, and saving the resulting access token + person URN so viralman can post to LinkedIn. Free, but the OAuth dance is the most involved of the three platforms.
level: 2
---

# viralman-login-linkedin

LinkedIn is the most complex of the three platforms because:

1. The app needs a **company/organization page** to be associated with — LinkedIn doesn't allow creating apps under a personal account alone. (You can create a free org page in 5 minutes.)
2. The `w_member_social` scope used to require app review, but as of late 2024 it's available under "Sign In with LinkedIn using OpenID Connect" + "Share on LinkedIn" products without review.
3. Tokens are short-lived (60 days for member tokens). Refreshing requires re-running this skill.

## Trigger phrases

Auto-trigger on:
- `/viralman-login-linkedin`
- "set up linkedin for viralman"
- "viralman 링크드인 연결", "viralman 링크드인 로그인"

## Boundaries

- **Never accept the access token in chat.** It's a bearer secret. `read -s` → `save_creds.py --stdin`.
- **Do not** WebFetch the LinkedIn developer portal — it's logged-in only.
- The OAuth flow runs in the user's browser; you don't simulate it. You print the URL, the user clicks, and then they paste the resulting `code` parameter into a `read -s` prompt.

## Step 1 — Create the app

Print verbatim:

```
1. Make sure you have (or create) a LinkedIn company page. From your home
   feed: "Work" menu → "Create a Company Page". A solo "page" is fine —
   it's just there because LinkedIn requires it.
2. Open https://www.linkedin.com/developers/apps and click "Create app".
     - App name:           viralman
     - LinkedIn Page:      <your company page>
     - App logo:           any image
     - Legal Agreement:    accept
3. In the new app's "Products" tab, REQUEST these two products (click "Request
   access" — both are auto-approved instantly):
     - "Sign In with LinkedIn using OpenID Connect"   (gives you `openid profile email`)
     - "Share on LinkedIn"                            (gives you `w_member_social`)
4. Go to the "Auth" tab. You'll see:
     - Client ID
     - Client Secret  (click the eye icon to reveal)
     - Redirect URLs  → ADD this exact URL:  http://localhost:8765/callback
   Click "Update" to save the redirect URL.
```

Wait for confirmation.

## Step 2 — Save the client_id (non-secret)

```bash
./scripts/save_creds.py --set LINKEDIN_CLIENT_ID=<client_id>
```

## Step 3 — Save the client_secret via `read -s`

```bash
read -rs -p 'LINKEDIN_CLIENT_SECRET: ' s && printf '%s' "$s" | \
  ./scripts/save_creds.py --stdin LINKEDIN_CLIENT_SECRET; unset s; echo
```

## Step 4 — Run the OAuth flow

LinkedIn requires browser-based authorization. Generate the auth URL by reading the saved client_id from the user's env (the agent can read this — it's not a secret) and constructing:

```
https://www.linkedin.com/oauth/v2/authorization
  ?response_type=code
  &client_id=<LINKEDIN_CLIENT_ID>
  &redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback
  &scope=openid%20profile%20email%20w_member_social
  &state=<random_8_chars>
```

Print the URL and tell the user:

```
1. Open this URL in your browser.
2. Click "Allow" to authorize viralman to post on your behalf.
3. After clicking Allow, your browser will be redirected to a localhost URL
   that won't load (that's expected — there's no server listening). Look at
   the address bar:

     http://localhost:8765/callback?code=AQT...long_string...&state=<...>

4. Copy the value of the `code` parameter — everything between `code=` and
   the next `&`.
```

Wait for the user to confirm they have the code.

## Step 5 — Exchange the code for an access token

The code is a one-time secret. Treat it the same way as the access token: pipe through `read -s`.

Have the user run:

```bash
read -rs -p 'LinkedIn auth code: ' code && \
  python3 - "$code" <<'PY'
import os, sys, urllib.parse, urllib.request, json
client_id = os.popen("./scripts/save_creds.py --show-keys").read()  # confirms env exists
# read client_id and client_secret directly via the creds lib
sys.path.insert(0, "scripts/lib")
from creds import load
c = load()
data = urllib.parse.urlencode({
    "grant_type": "authorization_code",
    "code": sys.argv[1],
    "redirect_uri": "http://localhost:8765/callback",
    "client_id": c["LINKEDIN_CLIENT_ID"],
    "client_secret": c["LINKEDIN_CLIENT_SECRET"],
}).encode()
req = urllib.request.Request("https://www.linkedin.com/oauth/v2/accessToken", data=data,
    headers={"Content-Type": "application/x-www-form-urlencoded"})
resp = json.loads(urllib.request.urlopen(req).read())
print("token_received_chars:", len(resp.get("access_token", "")))
import subprocess
subprocess.run(["./scripts/save_creds.py", "--stdin", "LINKEDIN_ACCESS_TOKEN"],
    input=resp["access_token"], text=True, check=True)
PY
unset code; echo
```

(That blob looks involved but it's the cleanest way to do the exchange without storing the code in shell history. The `read -rs` keeps the code out of history; the embedded Python does the POST and pipes the resulting token to `save_creds.py --stdin`.)

If the script prints `token_received_chars: <some_number>` and `saved: LINKEDIN_ACCESS_TOKEN`, the token is in the env file.

## Step 6 — Verify and capture the person URN

```bash
./scripts/check_creds.py --platform linkedin
```

Expected:

```
linkedin OK — <name> (sub=<long_id>)
hint: set LINKEDIN_PERSON_URN=urn:li:person:<long_id>
```

Take the hint and save the URN (not a secret):

```bash
./scripts/save_creds.py --set LINKEDIN_PERSON_URN=urn:li:person:<long_id>
```

Re-run `check_creds.py --platform linkedin` once more — the hint should disappear.

## Step 7 — Done + token expiry note

Tell the user:

```
LinkedIn is hooked up. Your access token expires in 60 days — re-run
/viralman-login-linkedin to refresh it. (You can skip Steps 1–3 next time;
just rerun Steps 4–6.)
```

## Failure modes to watch for

- `Bummer, something went wrong` on the auth page: the redirect URI in Step 1.4 doesn't exactly match `http://localhost:8765/callback`. Check for trailing slash or `https`.
- `401 invalid_token`: token expired (60-day cap) — re-run Steps 4–6.
- `403 ACCESS_DENIED` on POST: the Share on LinkedIn product wasn't added in Step 1.3.
