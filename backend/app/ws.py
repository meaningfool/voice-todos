import json
import logging

import logfire
import websockets
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.extract import extract_todos
from app.extraction_loop import ExtractionLoop
from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD
from app.live_session import LiveSessionController
from app.models import Todo
from app.session_recorder import SessionRecorder
from app.stt import SttSession
from app.stt_factory import create_stt_session as _create_stt_session
from app.stt_soniox import connect_soniox

logger = logging.getLogger(__name__)

router = APIRouter()

TOKEN_THRESHOLD = EXTRACTION_TOKEN_THRESHOLD


async def create_stt_session(
    settings,
    *,
    recorder: SessionRecorder | None = None,
) -> SttSession:
    return await _create_stt_session(
        settings,
        recorder=recorder,
        connect_soniox_fn=lambda api_key, **kwargs: connect_soniox(
            api_key,
            connect_fn=websockets.connect,
            **kwargs,
        ),
    )


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    settings = get_settings()
    controller: LiveSessionController | None = None
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

    async def handle_transcript_update(result) -> None:
        if result.tokens:
            await browser_ws.send_json(
                {
                    "type": "transcript",
                    "tokens": result.tokens,
                }
            )

        if extraction_loop is None:
            return

        if result.has_endpoint:
            await extraction_loop.on_endpoint()
        elif result.transcript_changed:
            extraction_loop.on_transcript_changed()

    async def handle_session_error(exc: Exception) -> None:
        logger.error("Error relaying from STT provider", exc_info=exc)
        await browser_ws.send_json({"type": "error", "message": str(exc)})

    with logfire.span("ws.connection_session", connection_id=connection_id):
        try:
            while True:
                ws_phase = "waiting_for_browser_message"
                message = await browser_ws.receive()

                if message.get("type") == "websocket.disconnect":
                    raise WebSocketDisconnect(
                        code=message.get("code", 1000),
                        reason=message.get("reason"),
                    )

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
                        if controller is not None:
                            await controller.close()
                            controller = None
                        if extraction_loop is not None:
                            extraction_loop.cancel()
                            extraction_loop = None
                        if recorder:
                            recorder.stop()

                        provider_name = settings.stt_provider
                        # Open the configured STT provider connection
                        try:
                            ws_phase = "connecting_to_stt"
                            if recorder:
                                recorder.start(provider_name=provider_name)
                            controller = LiveSessionController(
                                create_stt_session=create_stt_session,
                                on_update=handle_transcript_update,
                                on_error=handle_session_error,
                            )
                            latest_todo_items = []
                            todo_send_count = 0
                            extraction_loop = ExtractionLoop(
                                transcript=controller.transcript,
                                send_fn=send_todos,
                                extract_fn=extract_todos,
                                token_threshold=TOKEN_THRESHOLD,
                            )
                            await controller.start(
                                settings,
                                recorder=recorder,
                            )
                            ws_phase = "sending_started"
                            await browser_ws.send_json({"type": "started"})
                        except Exception as e:
                            logger.exception(
                                "Failed to connect to %s STT provider", provider_name
                            )
                            if extraction_loop is not None:
                                extraction_loop.cancel()
                                extraction_loop = None
                            if controller is not None:
                                await controller.close()
                                controller = None
                            if recorder:
                                recorder.stop()
                            await browser_ws.send_json(
                                {
                                    "type": "error",
                                    "message": (
                                        f"{provider_name} connection failed: {e}"
                                    ),
                                }
                            )

                    elif msg_type == "stop" and controller is not None:
                        logfire.info("ws.stop_received", connection_id=connection_id)
                        ws_phase = "stop"
                        stop_result = await controller.stop(
                            timeout_seconds=settings.soniox_stop_timeout_seconds,
                        )
                        warning_message: str | None = None
                        if stop_result.timed_out:
                            warning_message = (
                                "Timed out waiting for the final transcript; "
                                "todos were not extracted."
                            )
                            logger.warning(
                                "Timed out waiting for the final transcript to finish"
                            )

                        full_transcript = stop_result.transcript_text
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
                        controller = None

                # Binary message = audio frame
                elif "bytes" in message:
                    if controller is not None:
                        if recorder:
                            recorder.write_audio(message["bytes"])
                        await controller.send_audio(message["bytes"])

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
            if extraction_loop is not None:
                extraction_loop.cancel()
            if controller is not None:
                await controller.close()
