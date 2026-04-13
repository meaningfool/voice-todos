import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from starlette.testclient import TestClient

from app.extraction_thresholds import EXTRACTION_TOKEN_THRESHOLD
from app.main import app
from app.models import Todo
from app.stt import BoundaryState, SttCapabilities, SttEvent, SttToken
from app.ws import TOKEN_THRESHOLD


def _settings(**overrides):
    base = {
        "stt_provider": "soniox",
        "soniox_api_key": "soniox-test-key",
        "mistral_api_key": None,
        "record_sessions": False,
        "soniox_stop_timeout_seconds": 30.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _mock_soniox(messages=None):
    mock_soniox = AsyncMock()
    mock_soniox.send = AsyncMock()
    mock_soniox.close = AsyncMock()

    async def iterator():
        for message in messages or ['{"finished": true}']:
            yield message

    mock_soniox.__aiter__ = lambda self: iterator()
    return mock_soniox


def _mock_soniox_with_endpoints(transcripts_and_endpoints):
    mock_soniox = AsyncMock()
    mock_soniox.send = AsyncMock()
    mock_soniox.close = AsyncMock()

    messages = []
    for text, has_endpoint in transcripts_and_endpoints:
        tokens = [{"text": text, "is_final": True}]
        if has_endpoint:
            tokens.append({"text": "<end>", "is_final": True})
        messages.append(json.dumps({"tokens": tokens}))
    messages.append(json.dumps({"finished": True}))

    async def iterator():
        for message in messages:
            yield message

    mock_soniox.__aiter__ = lambda self: iterator()
    return mock_soniox


def test_ws_start_sends_started_when_soniox_connects():
    """A successful start returns a concrete started message."""
    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_connect.return_value = _mock_soniox()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

        soniox_config = json.loads(
            mock_connect.return_value.send.await_args_list[0].args[0]
        )
        assert soniox_config["enable_endpoint_detection"] is True
        assert soniox_config["max_endpoint_delay_ms"] == 1000


def test_ws_start_configures_extraction_loop_with_token_threshold():
    """The websocket layer wires the tuned token-threshold fallback into the loop."""
    extraction_loop = Mock()
    extraction_loop.cancel = Mock()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.ExtractionLoop", return_value=extraction_loop) as mock_loop_cls,
    ):
        mock_connect.return_value = _mock_soniox()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

        assert TOKEN_THRESHOLD == EXTRACTION_TOKEN_THRESHOLD
        assert mock_loop_cls.call_args.kwargs["token_threshold"] == TOKEN_THRESHOLD


def test_ws_start_surfaces_connect_errors():
    """Connection failures are returned as explicit errors."""
    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch(
            "app.ws.websockets.connect",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "boom" in response["message"]


def test_ws_mistral_start_surfaces_mistral_connect_error():
    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(side_effect=RuntimeError("boom")),
            create=True,
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            response = ws.receive_json()

    assert response == {
        "type": "error",
        "message": "mistral connection failed: boom",
    }


def test_ws_stop_without_start():
    """Sending stop without a prior start is handled gracefully (no-op)."""
    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_connect.return_value = _mock_soniox()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "stop"})
            # No Soniox session exists, so stop is a no-op.
            # Server stays in its receive loop — verify by sending another message.
            ws.send_json({"type": "start"})
            response = ws.receive_json()
            assert response["type"] == "started"


def test_ws_invalid_json_returns_error():
    """Malformed JSON is rejected without crashing the server."""
    with patch("app.ws.get_settings", return_value=_settings()):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_text("not-json")
            response = ws.receive_json()
            assert response == {
                "type": "error",
                "message": "Invalid control message",
            }


def test_ws_unknown_message_keeps_connection_alive():
    """Unknown message types are ignored and do not poison the socket."""
    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_connect.return_value = _mock_soniox()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"foo": "bar"})
            ws.send_json({"type": "start"})
            response = ws.receive_json()
            assert response == {"type": "started"}


def test_ws_disconnect_without_stop():
    """Disconnecting without sending stop does not crash the server."""
    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
    ):
        mock_connect.return_value = _mock_soniox()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}
        # The endpoint should clean up without raising.


def test_ws_disconnect_message_does_not_call_receive_again():
    """A disconnect frame should stop the receive loop before RuntimeError noise."""
    from app.ws import websocket_endpoint

    class FakeBrowserWebSocket:
        def __init__(self):
            self.receive_calls = 0

        async def accept(self):
            return None

        async def receive(self):
            self.receive_calls += 1
            if self.receive_calls == 1:
                return {"text": json.dumps({"type": "start"})}
            if self.receive_calls == 2:
                return {"type": "websocket.disconnect"}
            raise RuntimeError("receive called after disconnect")

        async def send_json(self, _payload):
            return None

    browser_ws = FakeBrowserWebSocket()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.logger.exception") as mock_logger_exception,
    ):
        mock_connect.return_value = _mock_soniox()

        asyncio.run(websocket_endpoint(browser_ws))

    assert browser_ws.receive_calls == 2
    mock_logger_exception.assert_not_called()


def test_ws_stop_sends_todos_before_stopped():
    """After stop, server sends todos then stopped — verifying the protocol sequence."""
    mock_todos = [Todo(text="Buy groceries", priority="high")]

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=mock_todos),
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json()["type"] == "started"

            ws.send_json({"type": "stop"})

            # Verify protocol: todos arrives before stopped
            todos_msg = ws.receive_json()
            assert todos_msg["type"] == "todos"
            assert len(todos_msg["items"]) == 1
            assert todos_msg["items"][0]["text"] == "Buy groceries"

            stopped_msg = ws.receive_json()
            assert stopped_msg["type"] == "stopped"


def test_ws_stop_emits_stop_timing_events():
    from starlette.websockets import WebSocket as StarletteWebSocket

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()

    timeline: list[str] = []
    original_send_json = StarletteWebSocket.send_json

    async def recording_send_json(self, message, *args, **kwargs):
        if isinstance(message, dict) and message.get("type") in {"todos", "stopped"}:
            timeline.append(f"send:{message['type']}")
        return await original_send_json(self, message, *args, **kwargs)

    def recording_logfire_info(event_name, *args, **kwargs):
        if event_name in {"ws.stop_received", "ws.stopped_sent"}:
            timeline.append(f"log:{event_name}")

    with (
        patch(
            "app.ws.logfire.info",
            side_effect=recording_logfire_info,
        ) as mock_logfire_info,
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=[]),
        patch("app.ws.WebSocket.send_json", new=recording_send_json),
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json()["type"] == "started"

            ws.send_json({"type": "stop"})
            _ = ws.receive_json()
            _ = ws.receive_json()

    event_names = [call.args[0] for call in mock_logfire_info.call_args_list]
    assert event_names == ["ws.stop_received", "ws.stopped_sent"]
    assert timeline == [
        "log:ws.stop_received",
        "send:todos",
        "log:ws.stopped_sent",
        "send:stopped",
    ]


def test_ws_sends_todos_during_recording():
    """Endpoint-triggered extraction can push todos before stop is requested."""
    mock_todos = [
        [Todo(text="Buy milk")],
        [Todo(text="Buy milk"), Todo(text="Call dentist")],
    ]

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.extract_todos", new_callable=AsyncMock, side_effect=mock_todos),
    ):
        mock_connect.return_value = _mock_soniox_with_endpoints(
            [
                ("I need to buy milk. ", True),
                ("And call the dentist. ", True),
            ]
        )

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            messages = [ws.receive_json() for _ in range(4)]

        todo_messages = [message for message in messages if message["type"] == "todos"]
        assert len(todo_messages) >= 1
        assert todo_messages[0]["items"][0]["text"] == "Buy milk"


def test_ws_stop_uses_finalized_transcript_for_final_pass():
    """The guaranteed final pass extracts only after relay-complete transcript state."""

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. Call the dentist. ")
        finalized_event.set()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_extract,
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})
            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json()["type"] == "stopped"

        mock_extract.assert_awaited_once_with(
            "Buy groceries. Call the dentist. ",
            previous_todos=None,
        )


def test_ws_stop_surfaces_final_extraction_failure():
    """A failing final pass still yields todos first, then stopped with a warning."""

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            assert ws.receive_json() == {"type": "todos", "items": []}
            stopped_msg = ws.receive_json()

        assert stopped_msg["type"] == "stopped"
        assert stopped_msg["warning"] == "Todo extraction failed."


def test_ws_stop_reuses_latest_snapshot_without_rerunning_final_extraction():
    """When stop sees an unchanged transcript, it still re-sends the latest snapshot."""

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        await extraction_loop.on_endpoint()
        finalized_event.set()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            side_effect=[
                [Todo(text="Buy groceries")],
                RuntimeError("should not re-extract"),
            ],
        ) as mock_extract,
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            assert ws.receive_json() == {
                "type": "todos",
                "items": [{"text": "Buy groceries"}],
            }

            ws.send_json({"type": "stop"})

            assert ws.receive_json() == {
                "type": "todos",
                "items": [{"text": "Buy groceries"}],
            }
            stopped_msg = ws.receive_json()

        assert stopped_msg == {
            "type": "stopped",
            "transcript": "Buy groceries. ",
        }
        assert mock_extract.await_count == 1


def test_ws_audio_frames_forward_without_session_recorder():
    """Binary audio frames still stream when recording is disabled."""
    with (
        patch("app.ws.get_settings", return_value=_settings(record_sessions=False)),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=[]),
    ):
        mock_soniox = _mock_soniox(messages=[])
        mock_connect.return_value = mock_soniox

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_bytes(b"\x00\x01")
            ws.send_json({"type": "stop"})

            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json()["type"] == "stopped"

            mock_soniox.send.assert_any_await(b"\x00\x01")


def test_ws_stop_waits_for_fin_not_finished():
    """Stop proceeds once finalization completes, even if relay shutdown lags behind."""
    release_relay = asyncio.Event()

    async def relay_with_fin(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()
        await release_relay.wait()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws._relay_stt_to_browser", side_effect=relay_with_fin),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[Todo(text="Buy groceries")],
        ),
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            todos_msg = ws.receive_json()
            stopped_msg = ws.receive_json()

        assert todos_msg["type"] == "todos"
        assert todos_msg["items"][0]["text"] == "Buy groceries"
        assert stopped_msg["type"] == "stopped"


def test_ws_stop_requests_final_transcript_before_end_of_stream():
    """Stop preserves the current Soniox finalize-then-EOS ordering."""

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        transcript.final_parts.append("Buy groceries. ")
        finalized_event.set()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_stt_to_browser",
            side_effect=relay_with_finalized_transcript,
        ),
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=[]),
    ):
        mock_soniox = _mock_soniox(messages=[])
        mock_connect.return_value = mock_soniox

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})
            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json()["type"] == "stopped"

        sends = mock_soniox.send.await_args_list
        assert sends[-2].args == (json.dumps({"type": "finalize"}),)
        assert sends[-1].args == (b"",)


class _FakeSttSession:
    def __init__(
        self,
        events=None,
        *,
        final_transcript_text=None,
        capabilities=None,
        per_event_delay: float = 0.0,
    ):
        self._events = list(events or [])
        self.capabilities = capabilities or SttCapabilities(
            exposes_finalization_boundary=True,
            exposes_endpoint_boundary=True,
        )
        self.final_transcript_text = final_transcript_text
        self._per_event_delay = per_event_delay
        self.send_audio = AsyncMock()
        self.request_final_transcript = AsyncMock()
        self.end_stream = AsyncMock()
        self.wait_for_final_transcript = AsyncMock()
        self.close = AsyncMock()

    async def _iterate(self):
        for event in self._events:
            if self._per_event_delay > 0:
                await asyncio.sleep(self._per_event_delay)
            yield event

    def __aiter__(self):
        return self._iterate()


def test_ws_uses_configured_stt_provider_factory():
    """Start should open the configured STT provider through the factory seam."""
    fake_session = _FakeSttSession()

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ) as mock_create_stt_session,
        patch(
            "app.ws.websockets.connect",
            new_callable=AsyncMock,
            side_effect=AssertionError("websocket transport should be hidden"),
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

        mock_create_stt_session.assert_awaited_once()


def test_ws_maps_stop_actions_through_provider_session():
    """Stop should use the app-level STT session actions, not Soniox transport calls."""
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy groceries. ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            )
        ]
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch(
            "app.ws.websockets.connect",
            new_callable=AsyncMock,
            side_effect=AssertionError("websocket transport should be hidden"),
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[Todo(text="Buy groceries")],
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            assert ws.receive_json()["type"] == "transcript"
            assert ws.receive_json()["type"] == "todos"
            assert ws.receive_json()["type"] == "stopped"

    fake_session.request_final_transcript.assert_awaited_once()
    fake_session.end_stream.assert_awaited_once()
    fake_session.wait_for_final_transcript.assert_awaited_once()


def test_ws_stop_uses_session_final_transcript_text_for_extraction_and_payload():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)
    extract_todos = AsyncMock(return_value=[Todo(text="Buy milk tomorrow")])

    with (
        patch("app.ws.get_settings", return_value=_settings(stt_provider="mistral")),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch("app.ws.extract_todos", new=extract_todos),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            transcript_msg = ws.receive_json()
            todos_msg = ws.receive_json()
            stopped_msg = ws.receive_json()

    assert transcript_msg == {
        "type": "transcript",
        "tokens": [{"text": "Buy milk", "is_final": True}],
    }
    extract_todos.assert_awaited_once_with("Buy milk tomorrow", previous_todos=None)
    assert todos_msg["type"] == "todos"
    assert stopped_msg == {
        "type": "stopped",
        "transcript": "Buy milk tomorrow",
    }


def test_ws_mistral_configured_session_streams_and_stops_with_final_done_text():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            transcript_msg = ws.receive_json()
            todos_msg = ws.receive_json()
            stopped_msg = ws.receive_json()

    assert transcript_msg == {
        "type": "transcript",
        "tokens": [{"text": "Buy milk", "is_final": True}],
    }
    assert todos_msg == {"type": "todos", "items": []}
    assert stopped_msg == {
        "type": "stopped",
        "transcript": "Buy milk tomorrow",
    }


def test_soniox_transcript_state_acceptance():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="buy mi", is_final=False)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            ),
            SttEvent(
                tokens=[SttToken(text="buy milk ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.NOT_OBSERVED,
            ),
        ],
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=[]),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            first_transcript = ws.receive_json()
            second_transcript = ws.receive_json()
            todos_msg = ws.receive_json()
            stopped_msg = ws.receive_json()

    assert first_transcript == {
        "type": "transcript",
        "tokens": [{"text": "buy mi", "is_final": False}],
    }
    assert second_transcript == {
        "type": "transcript",
        "tokens": [{"text": "buy milk ", "is_final": True}],
    }
    assert todos_msg == {"type": "todos", "items": []}
    assert stopped_msg == {
        "type": "stopped",
        "transcript": "buy milk ",
    }


def test_mistral_transcript_state_acceptance():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
            SttEvent(
                tokens=[SttToken(text=" tomorrow", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=[]),
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            first_transcript = ws.receive_json()
            second_transcript = ws.receive_json()
            todos_msg = ws.receive_json()
            stopped_msg = ws.receive_json()

    assert first_transcript == {
        "type": "transcript",
        "tokens": [{"text": "Buy milk", "is_final": True}],
    }
    assert second_transcript == {
        "type": "transcript",
        "tokens": [{"text": " tomorrow", "is_final": True}],
    }
    assert todos_msg == {"type": "todos", "items": []}
    assert stopped_msg == {
        "type": "stopped",
        "transcript": "Buy milk tomorrow",
    }


def test_threshold_trigger_acceptance():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
            SttEvent(
                tokens=[SttToken(text="milk ", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
            SttEvent(
                tokens=[SttToken(text="tomorrow", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            ),
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
        per_event_delay=0.02,
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch("app.ws.TOKEN_THRESHOLD", 3),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_extract,
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            assert ws.receive_json()["type"] == "transcript"
            assert mock_extract.await_count == 0

            assert ws.receive_json()["type"] == "transcript"
            assert mock_extract.await_count == 0

            assert ws.receive_json()["type"] == "transcript"
            assert ws.receive_json() == {"type": "todos", "items": []}

            ws.send_json({"type": "stop"})
            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json()["type"] == "stopped"

    assert mock_extract.await_count == 1


def test_unchanged_final_transcript_acceptance():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk tomorrow", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
        per_event_delay=0.01,
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch("app.ws.TOKEN_THRESHOLD", 3),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_extract,
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            assert ws.receive_json()["type"] == "transcript"
            assert ws.receive_json() == {"type": "todos", "items": []}
            ws.send_json({"type": "stop"})

            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json() == {
                "type": "stopped",
                "transcript": "Buy milk tomorrow",
            }

    assert mock_extract.await_count == 1


def test_changed_final_transcript_acceptance():
    fake_session = _FakeSttSession(
        events=[
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        ],
        final_transcript_text="Buy milk tomorrow",
        capabilities=SttCapabilities(
            exposes_finalization_boundary=False,
            exposes_endpoint_boundary=False,
        ),
        per_event_delay=0.01,
    )
    fake_session.wait_for_final_transcript = AsyncMock(return_value=None)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(
                stt_provider="mistral",
                mistral_api_key="mistral-test-key",
            ),
        ),
        patch("app.ws.TOKEN_THRESHOLD", 2),
        patch(
            "app.ws.create_stt_session",
            new=AsyncMock(return_value=fake_session),
            create=True,
        ),
        patch(
            "app.ws.extract_todos",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_extract,
    ):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            assert ws.receive_json()["type"] == "transcript"
            assert ws.receive_json() == {"type": "todos", "items": []}
            ws.send_json({"type": "stop"})

            assert ws.receive_json() == {"type": "todos", "items": []}
            assert ws.receive_json() == {
                "type": "stopped",
                "transcript": "Buy milk tomorrow",
            }

    assert mock_extract.await_count == 2


def test_ws_stop_timeout_skips_extraction_and_surfaces_warning():
    """A finalize timeout returns a warning instead of silent partial extraction."""
    relay_cancelled = asyncio.Event()

    async def slow_relay(
        _soniox_ws,
        _browser_ws,
        _transcript,
        _extraction_loop,
        _recorder=None,
        *,
        finalized_event,
    ):
        del finalized_event
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            relay_cancelled.set()
            raise

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(soniox_stop_timeout_seconds=0.01),
        ),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws._relay_stt_to_browser", side_effect=slow_relay),
        patch("app.ws.extract_todos", new_callable=AsyncMock) as mock_extract,
    ):
        mock_connect.return_value = _mock_soniox(messages=[])

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "start"})
            assert ws.receive_json() == {"type": "started"}

            ws.send_json({"type": "stop"})

            todos_msg = ws.receive_json()
            assert todos_msg == {"type": "todos", "items": []}
            assert relay_cancelled.is_set()

            stopped_msg = ws.receive_json()
            assert stopped_msg["type"] == "stopped"
            assert (
                stopped_msg["warning"]
                == "Timed out waiting for the final transcript; "
                "todos were not extracted."
            )
            mock_extract.assert_not_awaited()
