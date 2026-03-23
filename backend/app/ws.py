import asyncio
import contextlib
import json
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.extract import extract_todos

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
STOP_TIMEOUT_SECONDS = 5.0


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
    transcript_parts: list[str],
    interim_parts: list[str],
):
    """Read transcript events from Soniox and forward to browser."""
    try:
        async for message in soniox_ws:
            event = json.loads(message)
            if event.get("finished"):
                return
            tokens = event.get("tokens", [])
            if tokens:
                for t in tokens:
                    if t.get("is_final", False):
                        transcript_parts.append(t["text"])
                # Track latest interim text as fallback for extraction
                interim_text = "".join(t["text"] for t in tokens if not t.get("is_final", False))
                if interim_text:
                    interim_parts.clear()
                    interim_parts.append(interim_text)
                await browser_ws.send_json(
                    {
                        "type": "transcript",
                        "tokens": [
                            {"text": t["text"], "is_final": t.get("is_final", False)}
                            for t in tokens
                        ],
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

    soniox_ws = None
    relay_task = None
    transcript_parts: list[str] = []
    interim_parts: list[str] = []

    try:
        while True:
            message = await browser_ws.receive()

            # Text message = JSON control signal
            if "text" in message:
                data = json.loads(message["text"])
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
                        transcript_parts.clear()
                        interim_parts.clear()
                        relay_task = asyncio.create_task(
                            _relay_soniox_to_browser(
                                soniox_ws, browser_ws, transcript_parts, interim_parts
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
                    await soniox_ws.send(b"")  # Empty frame = end of audio
                    if relay_task:
                        try:
                            await asyncio.wait_for(
                                relay_task, timeout=STOP_TIMEOUT_SECONDS
                            )
                        except TimeoutError:
                            logger.warning(
                                "Timed out waiting for Soniox relay to finish"
                            )
                            relay_task.cancel()
                        finally:
                            relay_task = None

                    # Extract todos from accumulated transcript
                    # Use final tokens; fall back to interim if no finals arrived
                    full_transcript = "".join(transcript_parts)
                    if not full_transcript.strip() and interim_parts:
                        full_transcript = "".join(interim_parts)
                        logger.info("Using interim text as fallback for extraction")
                    logger.info(
                        "Transcript (%d chars): %s",
                        len(full_transcript),
                        full_transcript[:200],
                    )
                    try:
                        todos = await extract_todos(full_transcript)
                        logger.info("Extracted %d todos", len(todos))
                        await browser_ws.send_json(
                            {
                                "type": "todos",
                                "items": [
                                    t.model_dump(exclude_none=True)
                                    for t in todos
                                ],
                            }
                        )
                    except Exception:
                        logger.exception("Todo extraction failed")
                        await browser_ws.send_json(
                            {"type": "todos", "items": []}
                        )

                    await browser_ws.send_json({"type": "stopped"})

                    with contextlib.suppress(Exception):
                        await soniox_ws.close()
                    soniox_ws = None

            # Binary message = audio frame
            elif "bytes" in message:
                if soniox_ws:
                    await soniox_ws.send(message["bytes"])

    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if relay_task:
            relay_task.cancel()
        if soniox_ws:
            with contextlib.suppress(Exception):
                await soniox_ws.close()
