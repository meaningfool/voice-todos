import asyncio
import contextlib
import json
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.extract import extract_todos
from app.session_recorder import SessionRecorder
from app.transcript_accumulator import TranscriptAccumulator

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
    transcript: TranscriptAccumulator,
    recorder: SessionRecorder | None = None,
):
    """Read transcript events from Soniox and forward to browser."""
    try:
        async for message in soniox_ws:
            if recorder:
                recorder.write_soniox_message(
                    message if isinstance(message, str) else message.decode()
                )
            event = json.loads(message)
            if event.get("finished"):
                return
            tokens = transcript.apply_event(event)
            if tokens:
                await browser_ws.send_json(
                    {
                        "type": "transcript",
                        "tokens": tokens,
                    }
                )
    except websockets.ConnectionClosed:
        logger.warning("Soniox connection closed unexpectedly during relay")
    except Exception as e:
        logger.exception("Error relaying from Soniox")
        with contextlib.suppress(Exception):
            await browser_ws.send_json({"type": "error", "message": str(e)})


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    settings = get_settings()
    soniox_ws = None
    relay_task = None
    transcript = TranscriptAccumulator()
    recorder = SessionRecorder() if settings.record_sessions else None

    try:
        while True:
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
                    # If already connected, close existing connection first
                    if soniox_ws is not None:
                        if relay_task:
                            relay_task.cancel()
                            relay_task = None
                        with contextlib.suppress(Exception):
                            await soniox_ws.close()
                        soniox_ws = None
                    if recorder:
                        recorder.stop()

                    soniox_config = {
                        "api_key": settings.soniox_api_key,
                        "model": "stt-rt-v4",
                        "audio_format": "pcm_s16le",
                        "sample_rate": 16000,
                        "num_channels": 1,
                        "context": {
                            "general": [
                                {
                                    "key": "topic",
                                    "value": "The user is dictating tasks and todos "
                                    "into a voice-driven todo list application.",
                                },
                            ],
                        },
                    }

                    # Open Soniox connection
                    try:
                        soniox_ws = await websockets.connect(SONIOX_WS_URL)
                        await soniox_ws.send(json.dumps(soniox_config))
                        transcript.reset()
                        if recorder:
                            recorder.start()
                        relay_task = asyncio.create_task(
                            _relay_soniox_to_browser(
                                soniox_ws,
                                browser_ws,
                                transcript,
                                recorder,
                            )
                        )
                        await browser_ws.send_json({"type": "started"})
                    except Exception as e:
                        logger.exception("Failed to connect to Soniox")
                        await browser_ws.send_json(
                            {
                                "type": "error",
                                "message": f"Soniox connection failed: {e}",
                            }
                        )

                elif msg_type == "stop" and soniox_ws:
                    # Finalize forces Soniox to emit all pending interim
                    # tokens as final, then sends a <fin> marker token.
                    # Only after that do we send the empty frame to close.
                    await soniox_ws.send(json.dumps({"type": "finalize"}))
                    await soniox_ws.send(b"")  # Empty frame = end of stream
                    warning_message: str | None = None
                    if relay_task:
                        try:
                            await asyncio.wait_for(
                                relay_task,
                                timeout=settings.soniox_stop_timeout_seconds,
                            )
                        except TimeoutError:
                            warning_message = (
                                "Timed out waiting for the final transcript; "
                                "todos were not extracted."
                            )
                            logger.warning(
                                "Timed out waiting for Soniox relay to finish"
                            )
                            relay_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await relay_task
                        finally:
                            relay_task = None

                    # Extract todos from accumulated transcript
                    # Append trailing interim text that Soniox never finalized
                    full_transcript = transcript.full_text
                    logger.info(
                        "Transcript (%d chars): %s",
                        len(full_transcript),
                        full_transcript[:200],
                    )
                    todo_items: list[dict] = []
                    if not warning_message:
                        try:
                            todos = await extract_todos(full_transcript)
                            logger.info("Extracted %d todos", len(todos))
                            todo_items = [
                                t.model_dump(exclude_none=True, mode="json")
                                for t in todos
                            ]
                        except Exception:
                            warning_message = "Todo extraction failed."
                            logger.exception("Todo extraction failed")

                    await browser_ws.send_json({"type": "todos", "items": todo_items})

                    if recorder:
                        recorder.write_result(full_transcript, todo_items)
                        recorder.stop()

                    stopped_payload = {
                        "type": "stopped",
                        "transcript": full_transcript,
                    }
                    if warning_message:
                        stopped_payload["warning"] = warning_message
                    await browser_ws.send_json(stopped_payload)

                    with contextlib.suppress(Exception):
                        await soniox_ws.close()
                    soniox_ws = None

            # Binary message = audio frame
            elif "bytes" in message:
                if soniox_ws:
                    if recorder:
                        recorder.write_audio(message["bytes"])
                    await soniox_ws.send(message["bytes"])

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if recorder:
            recorder.stop()
        if relay_task:
            relay_task.cancel()
        if soniox_ws:
            with contextlib.suppress(Exception):
                await soniox_ws.close()
