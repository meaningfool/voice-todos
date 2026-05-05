from __future__ import annotations

from workers import Response, WorkerEntrypoint

from src.repo_bootstrap import bootstrap_backend_imports
from src.session_runtime import SessionRuntime

bootstrap_backend_imports()


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        del request
        return Response("Cloudflare session runtime scaffold", status=501)


__all__ = ["Default", "SessionRuntime"]
