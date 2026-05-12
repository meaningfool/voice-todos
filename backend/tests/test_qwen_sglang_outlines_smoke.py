from __future__ import annotations

import importlib
import io
import sys
from types import SimpleNamespace
from urllib import error


def test_probe_chat_completion_retries_transient_http_502(monkeypatch):
    class FakeChainable:
        @classmethod
        def from_name(cls, *args, **kwargs):
            return cls()

        @classmethod
        def from_registry(cls, *args, **kwargs):
            return cls()

        def entrypoint(self, *args, **kwargs):
            return self

        def pip_install(self, *args, **kwargs):
            return self

        def env(self, *args, **kwargs):
            return self

    class FakeApp:
        def __init__(self, *args, **kwargs):
            return None

        def cls(self, *args, **kwargs):
            return lambda obj: obj

        def local_entrypoint(self, *args, **kwargs):
            return lambda fn: fn

    fake_modal_experimental = SimpleNamespace(
        http_server=lambda **kwargs: lambda obj: obj
    )
    fake_modal = SimpleNamespace(
        Volume=FakeChainable,
        Image=FakeChainable,
        App=FakeApp,
        experimental=fake_modal_experimental,
        enter=lambda: lambda fn: fn,
        exit=lambda: lambda fn: fn,
        parameter=lambda default=None: default,
    )

    monkeypatch.setitem(sys.modules, "modal", fake_modal)
    monkeypatch.setitem(sys.modules, "modal.experimental", fake_modal_experimental)
    sys.modules.pop("scripts.qwen_sglang_outlines_smoke", None)
    smoke = importlib.import_module("scripts.qwen_sglang_outlines_smoke")

    responses = [
        error.HTTPError(
            url="https://modal.test/v1/chat/completions",
            code=502,
            msg="Bad Gateway",
            hdrs=None,
            fp=io.BytesIO(b"bad gateway"),
        ),
        {"choices": [{"message": {"content": "READY"}}]},
    ]

    def fake_json_request(
        url, *, payload=None, timeout=30, method="POST", headers=None
    ):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(smoke, "_json_request", fake_json_request)
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)

    response = smoke._probe_chat_completion(
        "https://modal.test",
        payload={"model": "Qwen/Qwen3.5-4B"},
        timeout=5,
        headers={"Modal-Session-ID": "session-123"},
    )

    assert response == {"choices": [{"message": {"content": "READY"}}]}


def test_probe_chat_completion_retries_connection_reset(monkeypatch):
    class FakeChainable:
        @classmethod
        def from_name(cls, *args, **kwargs):
            return cls()

        @classmethod
        def from_registry(cls, *args, **kwargs):
            return cls()

        def entrypoint(self, *args, **kwargs):
            return self

        def pip_install(self, *args, **kwargs):
            return self

        def env(self, *args, **kwargs):
            return self

    class FakeApp:
        def __init__(self, *args, **kwargs):
            return None

        def cls(self, *args, **kwargs):
            return lambda obj: obj

        def local_entrypoint(self, *args, **kwargs):
            return lambda fn: fn

    fake_modal_experimental = SimpleNamespace(
        http_server=lambda **kwargs: lambda obj: obj
    )
    fake_modal = SimpleNamespace(
        Volume=FakeChainable,
        Image=FakeChainable,
        App=FakeApp,
        experimental=fake_modal_experimental,
        enter=lambda: lambda fn: fn,
        exit=lambda: lambda fn: fn,
        parameter=lambda default=None: default,
    )

    monkeypatch.setitem(sys.modules, "modal", fake_modal)
    monkeypatch.setitem(sys.modules, "modal.experimental", fake_modal_experimental)
    sys.modules.pop("scripts.qwen_sglang_outlines_smoke", None)
    smoke = importlib.import_module("scripts.qwen_sglang_outlines_smoke")

    responses = [
        ConnectionResetError(54, "Connection reset by peer"),
        {"choices": [{"message": {"content": "READY"}}]},
    ]

    def fake_json_request(
        url, *, payload=None, timeout=30, method="POST", headers=None
    ):
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(smoke, "_json_request", fake_json_request)
    monkeypatch.setattr(smoke.time, "sleep", lambda _: None)

    response = smoke._probe_chat_completion(
        "https://modal.test",
        payload={"model": "Qwen/Qwen3.5-4B"},
        timeout=5,
        headers={"Modal-Session-ID": "session-123"},
    )

    assert response == {"choices": [{"message": {"content": "READY"}}]}
