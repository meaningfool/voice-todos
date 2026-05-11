#!/usr/bin/env bash

set -euo pipefail

URL="${1:-http://localhost:5173}"
FIXTURE="${2:-while-speaking-two-todos}"
SESSION="${AGENT_BROWSER_SESSION:-voice-todos-ui-smoke}"
WAIT_ATTEMPTS="${WAIT_ATTEMPTS:-50}"
WAIT_DELAY_SECONDS="${WAIT_DELAY_SECONDS:-0.2}"

eval_js() {
    agent-browser --session "$SESSION" eval "$1" | tr -d '\r'
}

wait_for_eval_truthy() {
    local expression="$1"
    local attempts=0

    while [ "$attempts" -lt "$WAIT_ATTEMPTS" ]; do
        if [ "$(eval_js "$expression" | tr -d '\n')" = "true" ]; then
            return 0
        fi
        attempts=$((attempts + 1))
        sleep "$WAIT_DELAY_SECONDS"
    done

    echo "Timed out waiting for expression: $expression" >&2
    return 1
}

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

wait_for_eval_truthy "document.querySelector('[data-testid=\"voice-app-shell\"]') !== null"
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-toggle\"]')?.textContent?.trim() === 'Start Session'"
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-dock\"]')?.dataset.status === 'idle'"

agent-browser --session "$SESSION" find text "Start Session" click >/dev/null
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-dock\"]')?.dataset.status === 'recording'"
wait_for_eval_truthy "document.querySelector('[data-testid=\"listening-indicator\"]')?.textContent?.trim() === 'Listening now...'"
wait_for_eval_truthy "document.querySelectorAll('[data-testid=\"todo-card-title\"]').length >= 1"
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-toggle\"]')?.textContent?.trim() === 'Finish Session'"

agent-browser --session "$SESSION" find text "Finish Session" click >/dev/null
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-dock\"]')?.dataset.status === 'idle'"
wait_for_eval_truthy "document.querySelector('[data-testid=\"session-toggle\"]')?.textContent?.trim() === 'Start Session'"

TODO_TEXTS_JSON="$(
    eval_js "JSON.stringify(Array.from(document.querySelectorAll('[data-testid=\"todo-card-title\"]')).map((node) => node.textContent?.trim()).filter(Boolean))"
)"
TRANSCRIPT_JSON="$(
    eval_js "JSON.stringify(document.querySelector('[data-testid=\"session-transcript\"]')?.textContent?.trim() ?? '')"
)"
WARNING_TEXT_JSON="$(
    eval_js "JSON.stringify(document.querySelector('[data-testid=\"warning-card\"]')?.textContent?.trim() ?? '')"
)"

python3 - "$TODO_TEXTS_JSON" "$TRANSCRIPT_JSON" "$WARNING_TEXT_JSON" <<'PY'
import json
import sys

todo_texts = json.loads(sys.argv[1])
transcript = json.loads(sys.argv[2])
warning_text = json.loads(sys.argv[3])

if isinstance(todo_texts, str):
    todo_texts = json.loads(todo_texts)
if isinstance(transcript, str) and transcript.startswith('"'):
    transcript = json.loads(transcript)
if isinstance(warning_text, str) and warning_text.startswith('"'):
    warning_text = json.loads(warning_text)

assert isinstance(todo_texts, list), todo_texts
assert len(todo_texts) >= 1, todo_texts
assert all(isinstance(text, str) and text.strip() for text in todo_texts), todo_texts
assert warning_text not in {
    "Microphone setup failed.",
    "WebSocket connection failed.",
    "Fixture audio setup failed.",
}, warning_text
PY

printf 'observed-todos: %s\n' "$TODO_TEXTS_JSON"
printf 'observed-transcript: %s\n' "$TRANSCRIPT_JSON"
printf 'observed-warning: %s\n' "$WARNING_TEXT_JSON"
echo "browser-ui-smoke: ok ($URL, fixture=$FIXTURE)"
