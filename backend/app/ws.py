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
from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD
from app.models import Todo
from app.session_recorder import SessionRecorder
from app.stt import SttSession
from app.stt_factory import create_stt_session as _create_stt_session
from app.stt_soniox import connect_soniox
from app.transcript_accumulator import TranscriptAccumulator

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


async def _relay_stt_to_browser(
    stt_session: SttSession,
    browser_ws: WebSocket,
    transcript: TranscriptAccumulator,
    extraction_loop: ExtractionLoop,
    recorder: SessionRecorder | None = None,
    *,
    finalized_event: asyncio.Event,
):
    """Read transcript events from the configured STT provider and forward them."""
    stt_event_count = 0
    browser_relay_count = 0
    with logfire.span("ws.stt_relay") as relay_span:
        try:
            async for event in stt_session:
                stt_event_count += 1

                if event.is_finished:
                    return

                result = transcript.apply_stt_event(event)
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
                elif result.transcript_changed:
                    extraction_loop.on_transcript_changed()
        except websockets.ConnectionClosed:
            logger.warning("STT connection closed unexpectedly during relay")
        except Exception as e:
            logger.exception("Error relaying from STT provider")
            with contextlib.suppress(Exception):
                await browser_ws.send_json({"type": "error", "message": str(e)})
        finally:
            relay_span.set_attribute("stt_event_count", stt_event_count)
            relay_span.set_attribute("browser_relay_count", browser_relay_count)


@router.websocket("/ws")
async def websocket_endpoint(browser_ws: WebSocket):
    await browser_ws.accept()

    settings = get_settings()
    stt_session = None
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
                        # If already connected, close existing connection first
                        if relay_task:
                            relay_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await relay_task
                            relay_task = None
                        if stt_session is not None:
                            with contextlib.suppress(Exception):
                                await stt_session.close()
                            stt_session = None
                        finalized_event = asyncio.Event()
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
                                recorder.start()
                            stt_session = await create_stt_session(
                                settings,
                                recorder=recorder,
                            )
                            transcript.reset()
                            latest_todo_items = []
                            todo_send_count = 0
                            extraction_loop = ExtractionLoop(
                                transcript=transcript,
                                send_fn=send_todos,
                                extract_fn=extract_todos,
                                token_threshold=TOKEN_THRESHOLD,
                            )
                            relay_task = asyncio.create_task(
                                _relay_stt_to_browser(
                                    stt_session,
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
                            logger.exception(
                                "Failed to connect to %s STT provider", provider_name
                            )
                            if extraction_loop is not None:
                                extraction_loop.cancel()
                                extraction_loop = None
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

                    elif msg_type == "stop" and stt_session:
                        logfire.info("ws.stop_received", connection_id=connection_id)
                        ws_phase = "stop_finalize"
                        await stt_session.request_final_transcript()
                        ws_phase = "stop_eos"
                        await stt_session.end_stream()
                        warning_message: str | None = None
                        try:
                            ws_phase = "stop_waiting_for_fin"
                            await asyncio.wait_for(
                                _wait_for_final_transcript(
                                    stt_session,
                                    finalized_event=finalized_event,
                                ),
                                timeout=settings.soniox_stop_timeout_seconds,
                            )
                        except TimeoutError:
                            warning_message = (
                                "Timed out waiting for the final transcript; "
                                "todos were not extracted."
                            )
                            logger.warning(
                                "Timed out waiting for the final transcript to finish"
                            )
                            if relay_task and not relay_task.done():
                                relay_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await relay_task
                                relay_task = None

                        full_transcript = (
                            stt_session.final_transcript_text
                            if stt_session.final_transcript_text is not None
                            else transcript.full_text
                        )
                        if stt_session.final_transcript_text is not None:
                            transcript.final_parts = [full_transcript]
                            transcript.interim_parts.clear()
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
                            await stt_session.close()
                        if relay_task and not relay_task.done():
                            relay_task.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await relay_task
                        relay_task = None
                        stt_session = None

                # Binary message = audio frame
                elif "bytes" in message:
                    if stt_session:
                        if recorder:
                            recorder.write_audio(message["bytes"])
                        await stt_session.send_audio(message["bytes"])

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
            if stt_session:
                with contextlib.suppress(Exception):
                    await stt_session.close()


async def _wait_for_final_transcript(
    stt_session: SttSession,
    *,
    finalized_event: asyncio.Event,
) -> None:
    wait_tasks = [
        asyncio.create_task(stt_session.wait_for_final_transcript()),
        asyncio.create_task(finalized_event.wait()),
    ]
    done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    for task in done:
        task.result()
