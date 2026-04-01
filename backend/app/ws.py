import asyncio
import contextlib
import json
import logging

import logfire
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.extract import extract_todos
from app.extraction_loop import ExtractionLoop
from app.models import Todo
from app.session_recorder import SessionRecorder
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
TOKEN_THRESHOLD = 15


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
    transcript: TranscriptAccumulator,
    extraction_loop: ExtractionLoop,
    recorder: SessionRecorder | None = None,
    *,
    finalized_event: asyncio.Event,
):
    """Read transcript events from Soniox and forward to browser."""
    soniox_event_count = 0
    browser_relay_count = 0
    with logfire.span("ws.soniox_relay") as relay_span:
        try:
            async for message in soniox_ws:
                if recorder:
                    recorder.write_soniox_message(
                        message if isinstance(message, str) else message.decode()
                    )
                event = json.loads(message)
                soniox_event_count += 1

                if event.get("finished"):
                    return

                result = transcript.apply_event(event)
                if result.has_fin:
                    finalized_event.set()
                tokens = result.tokens
                if tokens:
                    browser_relay_count += 1
                    await browser_ws.send_json(
                        {
                            "type": "transcript",
                            "tokens": tokens,
                        }
                    )

                if result.has_endpoint:
                    await extraction_loop.on_endpoint()
                elif result.final_token_count > 0:
                    extraction_loop.on_tokens(result.final_token_count)
        except websockets.ConnectionClosed:
            logger.warning("Soniox connection closed unexpectedly during relay")
        except Exception as e:
            logger.exception("Error relaying from Soniox")
            with contextlib.suppress(Exception):
                await browser_ws.send_json({"type": "error", "message": str(e)})
        finally:
            relay_span.set_attribute("soniox_event_count", soniox_event_count)
            relay_span.set_attribute("browser_relay_count", browser_relay_count)


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    settings = get_settings()
    soniox_ws = None
    relay_task = None
    finalized_event = asyncio.Event()
    transcript = TranscriptAccumulator()
    extraction_loop: ExtractionLoop | None = None
    recorder = SessionRecorder() if settings.record_sessions else None
    latest_todo_items: list[dict] = []
    todo_send_count = 0
    connection_id = id(browser_ws)
    ws_phase = "accepted"

    async def _send_todo_items(items: list[dict], *, remember_snapshot: bool) -> None:
        nonlocal latest_todo_items, todo_send_count

        payload_items = [dict(item) for item in items]
        with logfire.span(
            "ws.send_todos",
            connection_id=connection_id,
            todo_count=len(payload_items),
            remember_snapshot=remember_snapshot,
        ):
            await browser_ws.send_json({"type": "todos", "items": payload_items})

        if remember_snapshot:
            latest_todo_items = [dict(item) for item in payload_items]
        todo_send_count += 1

    async def send_todos(todos: list[Todo]) -> None:
        await _send_todo_items(
            [
                todo.model_dump(exclude_none=True, mode="json")
                for todo in todos
            ],
            remember_snapshot=True,
        )

    with logfire.span("ws.connection_session", connection_id=connection_id):
        try:
            while True:
                ws_phase = "waiting_for_browser_message"
                message = await browser_ws.receive()

                # Text message = JSON control signal
                if "text" in message:
                    try:
                        data = json.loads(message["text"])
                    except json.JSONDecodeError:
                        await browser_ws.send_json(
                            {"type": "error", "message": "Invalid control message"}
                        )
                        continue

                    msg_type = data.get("type")

                    if msg_type == "start":
                        ws_phase = "start"
                        # If already connected, close existing connection first
                        if relay_task:
                            relay_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await relay_task
                            relay_task = None
                        if soniox_ws is not None:
                            with contextlib.suppress(Exception):
                                await soniox_ws.close()
                            soniox_ws = None
                        finalized_event = asyncio.Event()
                        if extraction_loop is not None:
                            extraction_loop.cancel()
                            extraction_loop = None
                        if recorder:
                            recorder.stop()

                        soniox_config = {
                            "api_key": settings.soniox_api_key,
                            "model": "stt-rt-v4",
                            "audio_format": "pcm_s16le",
                            "sample_rate": 16000,
                            "num_channels": 1,
                            "enable_endpoint_detection": True,
                            "max_endpoint_delay_ms": 1000,
                            "context": {
                                "general": [
                                    {
                                        "key": "topic",
                                        "value": (
                                            "The user is dictating tasks and todos "
                                            "into a voice-driven todo list application."
                                        ),
                                    },
                                ],
                            },
                        }

                        # Open Soniox connection
                        try:
                            ws_phase = "connecting_to_soniox"
                            soniox_ws = await websockets.connect(SONIOX_WS_URL)
                            ws_phase = "sending_soniox_config"
                            await soniox_ws.send(json.dumps(soniox_config))
                            transcript.reset()
                            latest_todo_items = []
                            todo_send_count = 0
                            extraction_loop = ExtractionLoop(
                                transcript=transcript,
                                send_fn=send_todos,
                                extract_fn=extract_todos,
                                token_threshold=TOKEN_THRESHOLD,
                            )
                            if recorder:
                                recorder.start()
                            relay_task = asyncio.create_task(
                                _relay_soniox_to_browser(
                                    soniox_ws,
                                    browser_ws,
                                    transcript,
                                    extraction_loop,
                                    recorder,
                                    finalized_event=finalized_event,
                                )
                            )
                            ws_phase = "sending_started"
                            await browser_ws.send_json({"type": "started"})
                        except Exception as e:
                            logger.exception("Failed to connect to Soniox")
                            if extraction_loop is not None:
                                extraction_loop.cancel()
                                extraction_loop = None
                            await browser_ws.send_json(
                                {
                                    "type": "error",
                                    "message": f"Soniox connection failed: {e}",
                                }
                            )

                    elif msg_type == "stop" and soniox_ws:
                        logfire.info("ws.stop_received", connection_id=connection_id)
                        ws_phase = "stop_finalize"
                        # Finalize forces Soniox to emit all pending interim
                        # tokens as final, then sends a <fin> marker token.
                        # Only after that do we send the empty frame to close.
                        await soniox_ws.send(json.dumps({"type": "finalize"}))
                        ws_phase = "stop_eos"
                        await soniox_ws.send(b"")  # Empty frame = end of stream
                        warning_message: str | None = None
                        try:
                            # <fin> means Soniox has finalized transcript state for all
                            # prior audio; `finished` and socket close can happen later.
                            ws_phase = "stop_waiting_for_fin"
                            await asyncio.wait_for(
                                finalized_event.wait(),
                                timeout=settings.soniox_stop_timeout_seconds,
                            )
                        except TimeoutError:
                            warning_message = (
                                "Timed out waiting for the final transcript; "
                                "todos were not extracted."
                            )
                            logger.warning(
                                "Timed out waiting for Soniox finalization to finish"
                            )
                            if relay_task and not relay_task.done():
                                relay_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await relay_task
                                relay_task = None

                        full_transcript = transcript.full_text
                        logger.info(
                            "Transcript (%d chars): %s",
                            len(full_transcript),
                            full_transcript[:200],
                        )

                        todos_sent_before_stop = todo_send_count
                        if not warning_message and extraction_loop is not None:
                            try:
                                with logfire.span(
                                    "ws.final_extraction",
                                    connection_id=connection_id,
                                    transcript_chars=len(full_transcript),
                                ):
                                    ws_phase = "stop_final_extraction"
                                    await extraction_loop.on_stop()
                            except Exception:
                                warning_message = "Todo extraction failed."
                                logger.exception("Todo extraction failed")

                        if todo_send_count == todos_sent_before_stop:
                            ws_phase = "stop_sending_fallback_todos"
                            await _send_todo_items(
                                latest_todo_items,
                                remember_snapshot=False,
                            )

                        if recorder:
                            recorder.write_result(full_transcript, latest_todo_items)
                            recorder.stop()

                        stopped_payload = {
                            "type": "stopped",
                            "transcript": full_transcript,
                        }
                        if warning_message:
                            stopped_payload["warning"] = warning_message
                        ws_phase = "stop_sending_stopped"
                        logfire.info(
                            "ws.stopped_sent",
                            connection_id=connection_id,
                            transcript_chars=len(full_transcript),
                            warning=warning_message,
                        )
                        await browser_ws.send_json(stopped_payload)

                        if extraction_loop is not None:
                            extraction_loop.cancel()
                            extraction_loop = None
                        ws_phase = "stop_closing_soniox"
                        with contextlib.suppress(Exception):
                            await soniox_ws.close()
                        if relay_task and not relay_task.done():
                            relay_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await relay_task
                        relay_task = None
                        soniox_ws = None

                # Binary message = audio frame
                elif "bytes" in message:
                    if soniox_ws:
                        if recorder:
                            recorder.write_audio(message["bytes"])
                        await soniox_ws.send(message["bytes"])

        except WebSocketDisconnect:
            logger.info(
                "Browser websocket disconnected",
                extra={"connection_id": connection_id, "ws_phase": ws_phase},
            )
        except RuntimeError:
            logger.exception(
                "Browser websocket runtime error during %s",
                ws_phase,
                extra={"connection_id": connection_id, "ws_phase": ws_phase},
            )
        finally:
            if recorder:
                recorder.stop()
            if relay_task:
                relay_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await relay_task
            if extraction_loop is not None:
                extraction_loop.cancel()
            if soniox_ws:
                with contextlib.suppress(Exception):
                    await soniox_ws.close()
