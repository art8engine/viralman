#!/usr/bin/env bash
# Interactive credential wizard for viralman.
# Writes ~/.viralman/.env with mode 600. Re-runnable; preserves existing keys.

set -euo pipefail

CREDS_DIR="${HOME}/.viralman"
ENV_FILE="${CREDS_DIR}/.env"

mkdir -p "$CREDS_DIR"
chmod 700 "$CREDS_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  touch "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

# Load existing values so re-runs don't lose them.
declare -A EXISTING
while IFS='=' read -r k v; do
  [[ -z "$k" || "$k" =~ ^# ]] && continue
  v="${v%\"}"; v="${v#\"}"
  v="${v%\'}"; v="${v#\'}"
  EXISTING["$k"]="$v"
done < "$ENV_FILE"

ask() {
  local key="$1" prompt="$2" secret="${3:-0}"
  local current="${EXISTING[$key]:-}"
  local hint=""
  if [[ -n "$current" ]]; then
    if [[ "$secret" == "1" ]]; then
      hint=" [keep current ****${current: -4}]"
    else
      hint=" [keep current: $current]"
    fi
  fi
  local val
  if [[ "$secret" == "1" ]]; then
    read -r -s -p "${prompt}${hint}: " val; echo
  else
    read -r -p "${prompt}${hint}: " val
  fi
  if [[ -z "$val" ]]; then
    val="$current"
  fi
  EXISTING["$key"]="$val"
}

skip_q() {
  local prompt="$1"
  local ans
  read -r -p "$prompt [y/N]: " ans
  [[ "$ans" =~ ^[Yy]$ ]]
}

echo "==> viralman credential setup"
echo "    creds file: $ENV_FILE (mode 600)"
echo

# --- Reddit ---
echo "== Reddit (free) =="
echo "Register a 'script' app at https://www.reddit.com/prefs/apps"
if skip_q "configure Reddit?"; then
  ask REDDIT_CLIENT_ID "  client id" 0
  ask REDDIT_CLIENT_SECRET "  client secret" 1
  ask REDDIT_USERNAME "  reddit username" 0
  ask REDDIT_PASSWORD "  reddit password" 1
  ask REDDIT_USER_AGENT "  user agent (default viralman/0.1.0)" 0
fi
echo

# --- LinkedIn ---
echo "== LinkedIn (free, requires app review for w_member_social) =="
echo "Register at https://www.linkedin.com/developers/apps"
echo "After OAuth, you'll have an access token and your /me URN."
if skip_q "configure LinkedIn?"; then
  ask LINKEDIN_ACCESS_TOKEN "  access token (Bearer)" 1
  ask LINKEDIN_PERSON_URN "  person URN (urn:li:person:XXXX)" 0
fi
echo

# --- Twitter / X ---
echo "== X / Twitter (paid API for write) =="
echo "Skipping this works fine — viralman will open compose URLs instead."
if skip_q "configure X API access? (paid)"; then
  ask TWITTER_API_KEY "  API key" 1
  ask TWITTER_API_SECRET "  API secret" 1
  ask TWITTER_ACCESS_TOKEN "  access token" 1
  ask TWITTER_ACCESS_SECRET "  access token secret" 1
  ask TWITTER_HANDLE "  handle (without @)" 0
fi
echo

# Write back, atomically.
TMP="$(mktemp)"
{
  echo "# viralman credentials — do not commit"
  echo "# generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  for key in "${!EXISTING[@]}"; do
    val="${EXISTING[$key]}"
    [[ -z "$val" ]] && continue
    printf '%s="%s"\n' "$key" "$val"
  done
} > "$TMP"
mv "$TMP" "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "==> wrote $ENV_FILE"
echo "==> done. test with: ./scripts/post_twitter.py --no-open --body - <<< 'hello world'"
