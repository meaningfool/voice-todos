#!/usr/bin/env bash

set -euo pipefail

URL="${1:-http://localhost:5173}"
SESSION="${AGENT_BROWSER_SESSION:-voice-todos-ui-smoke}"

cleanup() {
    agent-browser --session "$SESSION" close >/dev/null 2>&1 || true
}

trap cleanup EXIT

agent-browser --session "$SESSION" open "$URL" >/dev/null
agent-browser --session "$SESSION" wait --load networkidle >/dev/null

SNAPSHOT="$(agent-browser --session "$SESSION" snapshot -i)"
printf '%s\n' "$SNAPSHOT" | grep -F "Voice Todos" >/dev/null
printf '%s\n' "$SNAPSHOT" | grep -F "Start Session" >/dev/null

HEADING_OK="$(
    cat <<'EOF' | agent-browser --session "$SESSION" eval --stdin
const heading = document.querySelector('h1')?.textContent?.trim();
heading === 'Voice Todos';
EOF
)"
test "$HEADING_OK" = "true"

BUTTON_OK="$(
    cat <<'EOF' | agent-browser --session "$SESSION" eval --stdin
const buttons = Array.from(document.querySelectorAll('button')).map((button) =>
  button.textContent?.replace(/\s+/g, ' ').trim()
);
buttons.includes('Start Session');
EOF
)"
test "$BUTTON_OK" = "true"

echo "browser-ui-smoke: ok ($URL)"
