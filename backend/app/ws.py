import asyncio
import contextlib
import json
import logging

import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"
STOP_TIMEOUT_SECONDS = 5.0


async def _relay_soniox_to_browser(
    soniox_ws: websockets.ClientConnection,
    browser_ws: WebSocket,
):
    """Read transcript events from Soniox and forward to browser."""
    try:
        async for message in soniox_ws:
            event = json.loads(message)
            if event.get("finished"):
                await browser_ws.send_json({"type": "stopped"})
                return
            tokens = event.get("tokens", [])
            if tokens:
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
                        "language_hints": ["fr"],
                        "language_hints_strict": True,
                        "context": {
                            "general": [
                                {"key": "domain", "value": "Task management"},
                                {
                                    "key": "topic",
                                    "value": "Voice-driven todo list application",
                                },
                            ],
                            "terms": ["todo", "todos"],
                        },
                    }

                    # Open Soniox connection
                    try:
                        soniox_ws = await websockets.connect(SONIOX_WS_URL)
                        await soniox_ws.send(json.dumps(soniox_config))
                        relay_task = asyncio.create_task(
                            _relay_soniox_to_browser(soniox_ws, browser_ws)
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
                    # Wait for relay task to finish (Soniox sends "finished")
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
                    with contextlib.suppress(Exception):
                        await soniox_ws.close()
                    soniox_ws = None

            # Binary message = audio frame
            elif "bytes" in message:
                if soniox_ws:
                    await soniox_ws.send(message["bytes"])

    except WebSocketDisconnect:
        pass
    finally:
        if relay_task:
            relay_task.cancel()
        if soniox_ws:
            with contextlib.suppress(Exception):
                await soniox_ws.close()
