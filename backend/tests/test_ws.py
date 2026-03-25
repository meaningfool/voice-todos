import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from starlette.testclient import TestClient

from app.main import app
from app.models import Todo
from app.ws import TOKEN_THRESHOLD


def _settings(**overrides):
    base = {
        "soniox_api_key": "soniox-test-key",
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
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not-json")
        response = ws.receive_json()
        assert response == {"type": "error", "message": "Invalid control message"}


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


def test_ws_stop_sends_todos_before_stopped():
    """After stop, server sends todos then stopped — verifying the protocol sequence."""
    mock_todos = [Todo(text="Buy groceries", priority="high")]

    async def relay_with_finalized_transcript(
        _soniox_ws,
        _browser_ws,
        transcript,
        _extraction_loop,
        _recorder=None,
    ):
        transcript.final_parts.append("Buy groceries. ")

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_soniox_to_browser",
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
    ):
        transcript.final_parts.append("Buy groceries. Call the dentist. ")

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_soniox_to_browser",
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
    ):
        transcript.final_parts.append("Buy groceries. ")

    with (
        patch("app.ws.get_settings", return_value=_settings()),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch(
            "app.ws._relay_soniox_to_browser",
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


def test_ws_stop_timeout_skips_extraction_and_surfaces_warning():
    """A finalize timeout returns a warning instead of silent partial extraction."""

    async def slow_relay(*args, **kwargs):
        await asyncio.sleep(1)

    with (
        patch(
            "app.ws.get_settings",
            return_value=_settings(soniox_stop_timeout_seconds=0.01),
        ),
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws._relay_soniox_to_browser", side_effect=slow_relay),
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

            stopped_msg = ws.receive_json()
            assert stopped_msg["type"] == "stopped"
            assert (
                stopped_msg["warning"]
                == "Timed out waiting for the final transcript; "
                "todos were not extracted."
            )
            mock_extract.assert_not_awaited()
