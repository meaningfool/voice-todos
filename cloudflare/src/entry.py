from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from repo_bootstrap import bootstrap_backend_imports
from session_runtime import SessionRuntime

bootstrap_backend_imports()

try:
    from workers import Response, WorkerEntrypoint
except ModuleNotFoundError:  # pragma: no cover - unavailable in local pytest
    class Response:
        def __init__(self, body=None, *, status: int = 200, headers=None) -> None:
            self.body = body
            self.status = status
            self.headers = headers or {}

    class WorkerEntrypoint:
        pass


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        url = urlparse(request.url)

        if url.path != "/ws":
            return Response("Not found", status=404)

        if request.method != "GET":
            return Response("Worker expected GET method", status=400)

        upgrade_header = request.headers.get("Upgrade")
        if not upgrade_header or upgrade_header.lower() != "websocket":
            return Response("Worker expected Upgrade: websocket", status=426)

        session_id = parse_qs(url.query).get("session", [None])[0]
        if not session_id:
            return Response("Missing session query parameter", status=400)

        stub = self.env.SESSION_RUNTIME.getByName(session_id)
        return await stub.fetch(request)


__all__ = ["Default", "SessionRuntime"]
