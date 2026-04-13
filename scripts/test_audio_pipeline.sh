#!/usr/bin/env bash
# Audio pipeline integration test.
#
# Verifies that no audio bytes are dropped between the browser's
# AudioWorklet and the backend WebSocket during the stop sequence.
#
# Strategy: count bytes on both sides and compare.
#   - Browser side: intercept ws.send() and count binary bytes
#   - Backend side: read audio.pcm from the recorded session
#   - Assert: they match (within 1 chunk tolerance)
#
# With the flush delay (correct code): all audio arrives before stop,
#   so backend records everything the browser sent.
# Without the flush delay (broken code): some audio arrives after the
#   backend has processed stop and closed the Soniox connection, so
#   those bytes are not recorded → audio.pcm < browser counter.
#
# Requirements:
#   - Backend on :8000, frontend on :5173
#   - agent-browser installed with Chrome engine

set -euo pipefail
cd "$(dirname "$0")/.."

RECORD_SECONDS=2
SESSIONS_DIR="sessions/recent"
MIN_AUDIO_BYTES=3200

echo "=== Audio Pipeline Integration Test ==="
echo ""

dump_debug_state() {
  echo "  Debug state:"
  agent-browser eval "JSON.stringify(window.__smokeDebug ?? [])" 2>&1 || true
}

# 1. Check servers
echo "Checking servers..."
curl -sf http://localhost:5173 > /dev/null || { echo "FAIL: Frontend not running on :5173"; exit 1; }
curl -sf http://localhost:8000/health > /dev/null || { echo "FAIL: Backend not running on :8000"; exit 1; }
echo "  Servers OK"

# 2. Clear recent sessions
echo "Clearing recent sessions..."
rm -rf "$SESSIONS_DIR"/*/
echo "  Cleared"

# 3. Open the app
echo "Opening browser..."
agent-browser --engine chrome open http://localhost:5173 > /dev/null 2>&1
echo "  Browser open"

# 4. Inject fake getUserMedia + byte counter on ws.send
echo "Injecting fake audio source + byte counter..."
agent-browser eval "
// Byte counter: intercept WebSocket.send for binary data
window.__audioBytesSent = 0;
const _origWsSend = WebSocket.prototype.send;
WebSocket.prototype.send = function(data) {
  if (data instanceof ArrayBuffer) {
    window.__audioBytesSent += data.byteLength;
  } else if (ArrayBuffer.isView(data)) {
    window.__audioBytesSent += data.byteLength;
  }
  return _origWsSend.call(this, data);
};

// Fake getUserMedia: OscillatorNode producing a 440Hz tone
const fakeGetUserMedia = async () => {
  const ctx = new AudioContext({ sampleRate: 16000 });
  const osc = ctx.createOscillator();
  osc.frequency.value = 440;
  const gain = ctx.createGain();
  gain.gain.value = 0.2;
  osc.start();
  const dest = ctx.createMediaStreamDestination();
  osc.connect(gain);
  gain.connect(dest);
  await ctx.resume();
  window.__fakeAudioContext = ctx;
  window.__fakeOscillator = osc;
  window.__fakeGain = gain;
  window.__fakeDestination = dest;
  return dest.stream;
};
Object.defineProperty(navigator.mediaDevices, 'getUserMedia', {
  configurable: true,
  writable: true,
  value: fakeGetUserMedia,
});
window.__fakeGetUserMediaInstalled =
  navigator.mediaDevices.getUserMedia === fakeGetUserMedia;
'injected'
" > /dev/null 2>&1
echo "  Injected"

# 5. Click Start
echo "Clicking Start..."
agent-browser find role button click --name "Start Session" > /dev/null 2>&1

# Wait for recording state
echo "  Waiting for recording state..."
for i in $(seq 1 10); do
  sleep 1
  STATE=$(agent-browser eval "document.querySelector('[data-status]')?.dataset.status ?? 'missing'" 2>&1 | tr -d '"')
  if [[ "$STATE" == "recording" ]]; then
    echo "  Recording started"
    break
  fi
  if [[ "$STATE" == "idle" ]]; then
    echo "FAIL: Connection failed — status returned to idle"
    dump_debug_state
    agent-browser close > /dev/null 2>&1
    exit 1
  fi
  if [ "$i" -eq 10 ]; then
    echo "FAIL: Timed out waiting for recording state, got: $STATE"
    dump_debug_state
    agent-browser close > /dev/null 2>&1
    exit 1
  fi
done

# 6. Wait for audio to actually flow before stopping
echo "Waiting for audio bytes..."
for i in $(seq 1 20); do
  sleep 1
  BROWSER_BYTES=$(agent-browser eval "window.__audioBytesSent" 2>&1 | tr -d '"')
  if [ "$BROWSER_BYTES" -ge "$MIN_AUDIO_BYTES" ]; then
    echo "  Audio flowing: $BROWSER_BYTES bytes"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "FAIL: Timed out waiting for audio bytes, got: $BROWSER_BYTES"
    dump_debug_state
    agent-browser close > /dev/null 2>&1
    exit 1
  fi
done

# 7. Record for N seconds
echo "Recording for ${RECORD_SECONDS}s..."
sleep "$RECORD_SECONDS"

# 8. Click Stop
echo "Clicking Stop..."
agent-browser find role button click --name "Finish Session" > /dev/null 2>&1
echo "  Stop clicked"

# 9. Wait for idle
echo "Waiting for extraction to complete..."
for i in $(seq 1 30); do
  sleep 1
  STATE=$(agent-browser eval "document.querySelector('[data-status]')?.dataset.status ?? 'missing'" 2>&1 | tr -d '"')
  if [[ "$STATE" == "idle" ]]; then
    echo "  Back to idle after ${i}s"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "FAIL: Timed out waiting for idle state, got: $STATE"
    dump_debug_state
    agent-browser close > /dev/null 2>&1
    exit 1
  fi
done

# 10. Read browser-side byte counter
BROWSER_BYTES=$(agent-browser eval "window.__audioBytesSent" 2>&1 | tr -d '"')
echo "  Browser sent: $BROWSER_BYTES bytes"

# 11. Close browser
agent-browser close > /dev/null 2>&1

# 12. Find the newest session and read audio.pcm size
NEWEST=$(ls -td "$SESSIONS_DIR"/*/ 2>/dev/null | head -1)
if [ -z "$NEWEST" ]; then
  echo "FAIL: No session recorded"
  exit 1
fi

AUDIO_FILE="${NEWEST}audio.pcm"
if [ ! -f "$AUDIO_FILE" ]; then
  echo "FAIL: No audio.pcm in session"
  exit 1
fi
BACKEND_BYTES=$(stat -f%z "$AUDIO_FILE")

# 13. Compare
echo ""
echo "=== Results ==="
echo "  Browser sent:     $BROWSER_BYTES bytes"
echo "  Backend received: $BACKEND_BYTES bytes"

if [ "$BROWSER_BYTES" -le 0 ]; then
  echo ""
  echo "FAIL: Browser sent no audio bytes"
  exit 1
fi

if [ "$BACKEND_BYTES" -le 0 ]; then
  echo ""
  echo "FAIL: Backend recorded no audio bytes"
  exit 1
fi

DIFF=$((BROWSER_BYTES - BACKEND_BYTES))
if [ "$DIFF" -lt 0 ]; then DIFF=$((-DIFF)); fi

# Allow up to 512 bytes difference (1-2 worklet chunks of rounding)
MAX_DIFF=512
echo "  Difference:       $DIFF bytes (max allowed: $MAX_DIFF)"

if [ "$DIFF" -le "$MAX_DIFF" ]; then
  echo ""
  echo "PASS: All audio bytes delivered to backend"
  exit 0
else
  echo ""
  echo "FAIL: Audio bytes dropped!"
  echo "  Browser sent $BROWSER_BYTES but backend only recorded $BACKEND_BYTES"
  echo "  Lost: $((BROWSER_BYTES - BACKEND_BYTES)) bytes"
  exit 1
fi
