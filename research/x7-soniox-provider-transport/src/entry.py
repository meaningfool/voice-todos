from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from urllib.parse import parse_qs, urlparse

from js import Uint8Array
from pyodide.ffi import create_proxy
from workers import DurableObject, Response, WorkerEntrypoint, fetch

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
SONIOX_FETCH_URL = "https://stt-rt.soniox.com/transcribe-websocket"
DEFAULT_CHUNK_SIZE = 3200
DEFAULT_CHUNK_DELAY_MS = 100


def _build_config(api_key: str) -> dict[str, object]:
    return {
        "api_key": api_key,
        "model": "stt-rt-v4",
        "audio_format": "pcm_s16le",
        "sample_rate": 16000,
        "num_channels": 1,
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": 1000,
    }


def _to_uint8_array(chunk: bytes):
    return Uint8Array.new(list(chunk))


class SonioxWebSocketClient:
    def __init__(self, ws) -> None:
        self.ws = ws
        self.opened = asyncio.Event()
        self.closed = asyncio.Event()
        self.messages: asyncio.Queue[str] = asyncio.Queue()
        self.error_message: str | None = None
        self.close_info: dict[str, object] | None = None
        self._proxies = []

        def on_open(event):
            del event
            self.opened.set()

        def on_message(event):
            self.messages.put_nowait(str(event.data))

        def on_error(event):
            self.error_message = f"websocket error: {event}"

        def on_close(event):
            self.close_info = {
                "code": getattr(event, "code", None),
                "reason": getattr(event, "reason", None),
                "was_clean": getattr(event, "wasClean", None),
            }
            self.closed.set()

        for event_name, handler in (
            ("open", on_open),
            ("message", on_message),
            ("error", on_error),
            ("close", on_close),
        ):
            proxy = create_proxy(handler)
            self._proxies.append(proxy)
            self.ws.addEventListener(event_name, proxy)

    @classmethod
    async def connect(cls, url: str):
        resp = await fetch(url, headers={"Upgrade": "websocket"})
        ws = resp.js_object.webSocket
        if not ws:
            raise RuntimeError("server did not accept the outbound websocket")
        ws.accept()
        client = cls(ws)
        client.opened.set()
        return client

    async def wait_until_open(self, timeout_seconds: float = 10.0) -> None:
        await asyncio.wait_for(self.opened.wait(), timeout=timeout_seconds)

    def send_text(self, payload: str) -> None:
        self.ws.send(payload)

    def send_binary(self, payload: bytes) -> None:
        self.ws.send(_to_uint8_array(payload))

    async def recv_json(self, timeout_seconds: float = 10.0) -> dict[str, object]:
        raw = await asyncio.wait_for(self.messages.get(), timeout=timeout_seconds)
        return json.loads(raw)

    async def wait_until_closed(self, timeout_seconds: float = 10.0) -> None:
        await asyncio.wait_for(self.closed.wait(), timeout=timeout_seconds)

    def close(self) -> None:
        self.ws.close()


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)

        if url.path == "/":
            return Response(
                json.dumps(
                    {
                        "ok": True,
                        "hint": "POST /prove-soniox with JSON {audio_b64, chunk_size?, chunk_delay_ms?} and ?finalize=1|0",
                    }
                ),
                headers={"content-type": "application/json"},
            )

        if url.path != "/prove-soniox":
            return Response("Not found", status=404)

        if request.method != "POST":
            return Response("Expected POST", status=405)

        session_name = f"soniox-proof-{uuid.uuid4().hex}"
        stub = self.env.SONIOX_TRANSPORT_PROOF.getByName(session_name)
        return await stub.fetch(request)


class SonioxTransportProof(DurableObject):
    def __init__(self, ctx, env):
        super().__init__(ctx, env)
        self.ctx = ctx
        self.env = env

    async def fetch(self, request):
        url = urlparse(request.url)
        query = parse_qs(url.query)
        use_finalize = query.get("finalize", ["1"])[0] == "1"

        started_at = time.perf_counter()

        try:
            payload = await request.json()
            audio_b64 = payload.get("audio_b64")
            if not isinstance(audio_b64, str):
                return Response.json(
                    {"ok": False, "error": "audio_b64 must be provided"},
                    status=400,
                )

            chunk_size = int(payload.get("chunk_size", DEFAULT_CHUNK_SIZE))
            chunk_delay_ms = int(payload.get("chunk_delay_ms", DEFAULT_CHUNK_DELAY_MS))
            audio = base64.b64decode(audio_b64)

            result = await self._prove(
                audio=audio,
                use_finalize=use_finalize,
                chunk_size=chunk_size,
                chunk_delay_ms=chunk_delay_ms,
            )
            result["elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
            return Response.json(result)
        except Exception as exc:
            return Response.json(
                {
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_ms": int((time.perf_counter() - started_at) * 1000),
                },
                status=500,
            )

    async def _prove(
        self,
        *,
        audio: bytes,
        use_finalize: bool,
        chunk_size: int,
        chunk_delay_ms: int,
    ) -> dict[str, object]:
        stage = "connect"
        client = None
        saw_fin = False
        saw_finished = False
        final_tokens: list[str] = []
        events_seen = 0
        termination_reason: str | None = None

        try:
            client = await SonioxWebSocketClient.connect(SONIOX_FETCH_URL)
            await client.wait_until_open()
            stage = "send_config"
            client.send_text(json.dumps(_build_config(self.env.SONIOX_API_KEY)))

            stage = "stream_audio"
            for index in range(0, len(audio), chunk_size):
                client.send_binary(audio[index : index + chunk_size])
                await asyncio.sleep(chunk_delay_ms / 1000)

            if use_finalize:
                stage = "send_finalize"
                client.send_text(json.dumps({"type": "finalize"}))
            stage = "send_eos"
            client.send_binary(b"")

            stage = "read_events"
            while True:
                try:
                    event = await client.recv_json(timeout_seconds=3.0)
                except TimeoutError:
                    if use_finalize and saw_fin:
                        termination_reason = "finalization_observed"
                        break
                    if not use_finalize and events_seen > 0:
                        termination_reason = "idle_after_partial_transcript"
                        break
                    raise
                events_seen += 1

                if event.get("finished"):
                    saw_finished = True
                    termination_reason = "provider_finished"
                    break

                for token in event.get("tokens", []):
                    if token.get("text") == "<fin>":
                        saw_fin = True
                        continue
                    if token.get("is_final"):
                        final_tokens.append(token["text"])

            transcript = "".join(final_tokens)
            stage = "close_client"
            client.close()
            stage = "wait_close"
            try:
                await client.wait_until_closed(timeout_seconds=5.0)
            except TimeoutError:
                pass

            return {
                "ok": True,
                "use_finalize": use_finalize,
                "transcript": transcript,
                "saw_fin": saw_fin,
                "saw_finished": saw_finished,
                "events_seen": events_seen,
                "termination_reason": termination_reason,
                "close_info": client.close_info,
                "error_message": client.error_message,
            }
        except Exception as exc:
            raise RuntimeError(
                f"stage={stage} events_seen={events_seen} "
                f"saw_fin={saw_fin} saw_finished={saw_finished} "
                f"partial_transcript={''.join(final_tokens)!r} "
                f"close_info={None if client is None else client.close_info} "
                f"error_message={None if client is None else client.error_message} "
                f"inner={type(exc).__name__}: {exc}"
            ) from exc
        finally:
            if client is not None and not client.closed.is_set():
                client.close()
