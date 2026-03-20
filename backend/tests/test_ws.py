from starlette.testclient import TestClient

from app.main import app


def test_ws_endpoint_accepts_connection():
    """WebSocket endpoint accepts a connection and responds to start."""
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "start"})
        # Should get either a "started" or "error" response
        response = ws.receive_json()
        assert response["type"] in ("started", "error")
