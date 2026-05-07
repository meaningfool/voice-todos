from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.entry import Default


class _FakeRequest:
    def __init__(
        self,
        url: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.method = method
        self.headers = headers or {"Upgrade": "websocket"}


class _FakeSessionRuntimeNamespace:
    def __init__(self) -> None:
        self.session_names: list[str] = []

    def getByName(self, session_name: str):
        self.session_names.append(session_name)
        return _FakeSessionStub(session_name)


class _FakeSessionStub:
    def __init__(self, session_name: str) -> None:
        self.session_name = session_name

    async def fetch(self, request):
        return SimpleNamespace(status=101, request=request, session_name=self.session_name)


def _worker(namespace: _FakeSessionRuntimeNamespace) -> Default:
    worker = Default()
    worker.env = SimpleNamespace(SESSION_RUNTIME=namespace)
    return worker


@pytest.mark.asyncio
async def test_worker_accepts_plain_ws_without_session_query() -> None:
    namespace = _FakeSessionRuntimeNamespace()
    request = _FakeRequest("https://example.com/ws")

    response = await _worker(namespace).fetch(request)

    assert response.status == 101
    assert namespace.session_names
    assert namespace.session_names[0]


@pytest.mark.asyncio
async def test_worker_preserves_explicit_session_query() -> None:
    namespace = _FakeSessionRuntimeNamespace()
    request = _FakeRequest("https://example.com/ws?session=smoke-todo-stop")

    response = await _worker(namespace).fetch(request)

    assert response.status == 101
    assert namespace.session_names == ["smoke-todo-stop"]
