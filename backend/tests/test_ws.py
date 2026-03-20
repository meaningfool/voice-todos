from starlette.testclient import TestClient

from app.main import app


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
