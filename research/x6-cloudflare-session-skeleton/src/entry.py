from __future__ import annotations

import asyncio
import json
import time
from textwrap import dedent
from urllib.parse import parse_qs, urlparse

from js import WebSocketPair
from workers import DurableObject, Response, WorkerEntrypoint

SESSION_CAP_MS = 5_000
FINAL_TRANSCRIPT = "Buy milk and call mom."
TODOS = [
    {"text": "Buy milk", "category": "errands"},
    {"text": "Call mom", "priority": "high"},
]


def html_page() -> str:
    return dedent(
        f"""\
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <title>Spike X6 Session Skeleton</title>
            <style>
              :root {{
                color-scheme: dark;
                font-family: Inter, ui-sans-serif, system-ui, sans-serif;
              }}
              body {{
                margin: 0;
                background: #0f1115;
                color: #f4f7fb;
              }}
              main {{
                max-width: 860px;
                margin: 0 auto;
                padding: 32px 20px 48px;
              }}
              h1 {{
                margin: 0 0 8px;
                font-size: 28px;
              }}
              p {{
                color: #b3bfcc;
                margin: 0 0 20px;
              }}
              .toolbar {{
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
                margin-bottom: 16px;
              }}
              button {{
                border: 1px solid #344156;
                background: #1a2230;
                color: #f4f7fb;
                padding: 10px 14px;
                border-radius: 6px;
                cursor: pointer;
                font: inherit;
              }}
              button:disabled {{
                opacity: 0.45;
                cursor: default;
              }}
              .meta {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                gap: 12px;
                margin-bottom: 16px;
              }}
              .panel {{
                background: #151b24;
                border: 1px solid #243042;
                border-radius: 8px;
                padding: 14px;
              }}
              .label {{
                display: block;
                color: #8fa2b6;
                font-size: 12px;
                margin-bottom: 6px;
                text-transform: uppercase;
              }}
              pre {{
                margin: 0;
                white-space: pre-wrap;
                overflow-wrap: anywhere;
                font-size: 13px;
                line-height: 1.5;
              }}
            </style>
          </head>
          <body>
            <main>
              <h1>Spike X6: local session skeleton</h1>
              <p>
                Minimal Python Worker + Durable Object prototype. Session cap is
                <strong>{SESSION_CAP_MS / 1000:.0f}s</strong>.
              </p>
              <div class="toolbar">
                <button id="connect">Connect</button>
                <button id="start" disabled>Send start</button>
                <button id="audio" disabled>Send binary chunk</button>
                <button id="stop" disabled>Send stop</button>
                <button id="reset">New session id</button>
              </div>
              <div class="meta">
                <div class="panel">
                  <span class="label">Session id</span>
                  <pre id="session"></pre>
                </div>
                <div class="panel">
                  <span class="label">Status</span>
                  <pre id="status">idle</pre>
                </div>
              </div>
              <div class="panel">
                <span class="label">Event log</span>
                <pre id="log"></pre>
              </div>
            </main>
            <script>
              const connectButton = document.getElementById("connect");
              const startButton = document.getElementById("start");
              const audioButton = document.getElementById("audio");
              const stopButton = document.getElementById("stop");
              const resetButton = document.getElementById("reset");
              const sessionEl = document.getElementById("session");
              const statusEl = document.getElementById("status");
              const logEl = document.getElementById("log");

              let ws = null;
              let sessionId = crypto.randomUUID();

              function setStatus(next) {{
                statusEl.textContent = next;
              }}

              function appendLog(line) {{
                const stamp = new Date().toISOString().slice(11, 23);
                logEl.textContent += `[${{stamp}}] ${{line}}\\n`;
              }}

              function setSession(next) {{
                sessionId = next;
                sessionEl.textContent = sessionId;
              }}

              function updateButtons() {{
                const open = ws && ws.readyState === WebSocket.OPEN;
                connectButton.disabled = open;
                startButton.disabled = !open;
                audioButton.disabled = !open;
                stopButton.disabled = !open;
              }}

              setSession(sessionId);
              updateButtons();

              connectButton.addEventListener("click", () => {{
                const protocol = location.protocol === "https:" ? "wss:" : "ws:";
                ws = new WebSocket(`${{protocol}}//${{location.host}}/ws?session=${{encodeURIComponent(sessionId)}}`);
                setStatus("connecting");
                appendLog(`opening websocket for session ${{sessionId}}`);
                updateButtons();

                ws.onopen = () => {{
                  setStatus("connected");
                  appendLog("socket opened");
                  updateButtons();
                }};

                ws.onmessage = (event) => {{
                  appendLog(`server -> ${{event.data}}`);
                  try {{
                    const payload = JSON.parse(event.data);
                    if (payload.type === "started") setStatus("recording");
                    if (payload.type === "stopped") setStatus("stopped");
                  }} catch (_err) {{
                    // keep log only
                  }}
                }};

                ws.onerror = () => {{
                  appendLog("socket error");
                  setStatus("error");
                }};

                ws.onclose = (event) => {{
                  appendLog(`socket closed code=${{event.code}} reason=${{event.reason || "(none)"}}`);
                  setStatus("closed");
                  updateButtons();
                }};
              }});

              startButton.addEventListener("click", () => {{
                ws.send(JSON.stringify({{ type: "start" }}));
                appendLog('client -> {{"type":"start"}}');
              }});

              audioButton.addEventListener("click", () => {{
                ws.send(new Uint8Array([1, 2, 3, 4]).buffer);
                appendLog("client -> <4-byte binary chunk>");
              }});

              stopButton.addEventListener("click", () => {{
                ws.send(JSON.stringify({{ type: "stop" }}));
                appendLog('client -> {{"type":"stop"}}');
              }});

              resetButton.addEventListener("click", () => {{
                if (ws && ws.readyState === WebSocket.OPEN) {{
                  appendLog("close current socket before resetting the session id");
                  return;
                }}
                logEl.textContent = "";
                setStatus("idle");
                setSession(crypto.randomUUID());
                updateButtons();
              }});
            </script>
          </body>
        </html>
        """
    )


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)

        if url.path == "/":
            return Response(
                html_page(),
                headers={"content-type": "text/html; charset=utf-8"},
            )

        if url.path != "/ws":
            return Response("Not found", status=404)

        if request.method != "GET":
            return Response("Worker expected GET method", status=400)

        upgrade_header = request.headers.get("Upgrade")
        if not upgrade_header or upgrade_header.lower() != "websocket":
            return Response("Worker expected Upgrade: websocket", status=426)

        session_id = parse_qs(url.query).get("session", [None])[0]
        if not session_id:
            return Response("Missing session query parameter", status=400)

        stub = self.env.SESSION_RUNTIME.getByName(session_id)
        return await stub.fetch(request)


class SessionRuntime(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env
        self.storage = ctx.storage
        self.started = False
        self.session_id = "unknown"

    async def fetch(self, request):
        url = urlparse(request.url)
        self.session_id = parse_qs(url.query).get("session", ["unknown"])[0]

        client, server = WebSocketPair.new().object_values()
        self.ctx.acceptWebSocket(server)

        return Response(
            None,
            status=101,
            web_socket=client,
        )

    async def webSocketMessage(self, ws, message):
        if not isinstance(message, str):
            return

        try:
            payload = json.loads(str(message))
        except json.JSONDecodeError:
            ws.send(json.dumps({"type": "error", "message": "Invalid control message"}))
            return

        message_type = payload.get("type")

        if message_type == "start":
            if self.started:
                return

            self.started = True
            self.storage.setAlarm(int(time.time() * 1000) + SESSION_CAP_MS)

            ws.send(json.dumps({"type": "started"}))
            await asyncio.sleep(0.1)
            ws.send(
                json.dumps(
                    {
                        "type": "transcript",
                        "tokens": [
                            {"text": "Buy ", "is_final": False},
                            {"text": "milk", "is_final": False},
                        ],
                    }
                )
            )
            await asyncio.sleep(0.1)
            ws.send(
                json.dumps(
                    {
                        "type": "transcript",
                        "tokens": [
                            {"text": "Buy milk ", "is_final": True},
                            {"text": "and call mom.", "is_final": True},
                        ],
                    }
                )
            )
            await asyncio.sleep(0.1)
            ws.send(json.dumps({"type": "todos", "items": TODOS}))
            return

        if message_type == "stop":
            await self._finish(ws, warning="Stopped by client.")
            return

        ws.send(
            json.dumps(
                {
                    "type": "error",
                    "message": f"Unsupported control message: {message_type!r}",
                }
            )
        )

    async def alarm(self, alarm_info=None):
        for ws in self.ctx.getWebSockets():
            await self._finish(ws, warning="Spike session cap reached.")

    async def webSocketClose(self, ws, code, reason, was_clean):
        self.started = False
        ws.close(code, reason)

    async def _finish(self, ws, *, warning: str):
        if ws.readyState != 1:
            return

        ws.send(
            json.dumps(
                {
                    "type": "stopped",
                    "transcript": FINAL_TRANSCRIPT,
                    "warning": warning,
                }
            )
        )
        self.started = False
        ws.close(1000, warning)
