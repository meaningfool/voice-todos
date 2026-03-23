from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from app.main import app
from app.models import Todo


def test_ws_endpoint_accepts_connection():
    """WebSocket endpoint accepts a connection and responds to start."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        response = ws.receive_json()
        assert response["type"] in ("started", "error")


def test_ws_start_responds():
    """Start always responds with either started or error."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        response = ws.receive_json()
        # Soniox may accept or reject — either response is valid
        assert response["type"] in ("started", "error")


def test_ws_stop_without_start():
    """Sending stop without a prior start is handled gracefully (no-op)."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "stop"})
        # No Soniox session exists, so stop is a no-op.
        # Server stays in its receive loop — verify by sending another message.
        ws.send_json({"type": "start"})
        response = ws.receive_json()
        assert response["type"] in ("started", "error")


def test_ws_malformed_message():
    """A JSON message without a 'type' field does not crash the endpoint."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"foo": "bar"})
        # Unknown message type is ignored. Verify server is still alive.
        ws.send_json({"type": "start"})
        response = ws.receive_json()
        assert response["type"] in ("started", "error")


def test_ws_disconnect_without_stop():
    """Disconnecting without sending stop does not crash the server."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        response = ws.receive_json()
        assert response["type"] in ("started", "error")
    # WebSocket closed without sending stop — server should clean up gracefully


def test_ws_stop_sends_todos_before_stopped():
    """After stop, server sends todos then stopped — verifying the protocol sequence."""
    mock_todos = [Todo(text="Buy groceries", priority="high")]

    with (
        patch("app.ws.websockets.connect", new_callable=AsyncMock) as mock_connect,
        patch("app.ws.extract_todos", new_callable=AsyncMock, return_value=mock_todos),
    ):
        # Fake Soniox connection that immediately signals "finished"
        mock_soniox = AsyncMock()
        mock_soniox.send = AsyncMock()
        mock_soniox.close = AsyncMock()

        async def soniox_messages():
            yield '{"finished": true}'

        mock_soniox.__aiter__ = lambda self: soniox_messages()
        mock_connect.return_value = mock_soniox

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
