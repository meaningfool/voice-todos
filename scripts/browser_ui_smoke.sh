#!/usr/bin/env bash

set -euo pipefail

URL="${1:-http://localhost:5173}"
FIXTURE="${2:-while-speaking-two-todos}"
SESSION="${AGENT_BROWSER_SESSION:-voice-todos-ui-smoke}"

cleanup() {
    agent-browser --session "$SESSION" close >/dev/null 2>&1 || true
}

trap cleanup EXIT

if [ "$FIXTURE" != "while-speaking-two-todos" ]; then
    echo "Unsupported fixture: $FIXTURE" >&2
    exit 1
fi

agent-browser --session "$SESSION" open "$URL/?fixture=$FIXTURE" >/dev/null
agent-browser --session "$SESSION" wait --load networkidle >/dev/null

SNAPSHOT="$(agent-browser --session "$SESSION" snapshot -i)"
printf '%s\n' "$SNAPSHOT" | grep -F "Voice Todos" >/dev/null
printf '%s\n' "$SNAPSHOT" | grep -F "Start Session" >/dev/null

agent-browser --session "$SESSION" find text "Start Session" click >/dev/null
agent-browser --session "$SESSION" wait --text "Buy oat milk" >/dev/null

DURING_RUN_SNAPSHOT="$(
    agent-browser --session "$SESSION" snapshot
)"
printf '%s\n' "$DURING_RUN_SNAPSHOT" | grep -F "Buy oat milk" >/dev/null
printf '%s\n' "$DURING_RUN_SNAPSHOT" | grep -F "Finish Session" >/dev/null

agent-browser --session "$SESSION" find text "Finish Session" click >/dev/null
agent-browser --session "$SESSION" wait --text "Start Session" >/dev/null

TODO_TEXTS_JSON="$(
    agent-browser --session "$SESSION" eval "JSON.stringify(Array.from(document.querySelectorAll('article p')).map((node) => node.textContent?.trim()).filter(Boolean))"
)"
TRANSCRIPT_JSON="$(
    agent-browser --session "$SESSION" eval "JSON.stringify(document.querySelector('.voice-session-transcript')?.textContent?.trim() ?? '')"
)"
BODY_TEXT_JSON="$(
    agent-browser --session "$SESSION" eval "JSON.stringify(document.body.innerText)"
)"

python3 - "$TODO_TEXTS_JSON" "$TRANSCRIPT_JSON" "$BODY_TEXT_JSON" <<'PY'
import json
import sys

todo_texts = json.loads(sys.argv[1])
transcript = json.loads(sys.argv[2])
body_text = json.loads(sys.argv[3])

if isinstance(todo_texts, str):
    todo_texts = json.loads(todo_texts)
if isinstance(transcript, str) and transcript.startswith('"'):
    transcript = json.loads(transcript)
if isinstance(body_text, str) and body_text.startswith('"'):
    body_text = json.loads(body_text)

assert "Buy oat milk" in todo_texts, todo_texts
assert any("Sarah" in text and "budget" in text for text in todo_texts), todo_texts
assert "oat milk tonight" in transcript.lower(), transcript
assert "sarah" in transcript.lower(), transcript
assert "budget" in transcript.lower(), transcript
assert "Microphone setup failed." not in body_text, body_text
PY

echo "browser-ui-smoke: ok ($URL, fixture=$FIXTURE)"
