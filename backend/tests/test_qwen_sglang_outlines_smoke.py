from __future__ import annotations

import asyncio
import importlib
import io
import sys
from types import SimpleNamespace
from urllib import error

import pytest


def _load_smoke_module(monkeypatch):
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

        def add_local_file(self, *args, **kwargs):
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
    return importlib.import_module("scripts.qwen_sglang_outlines_smoke")


def _load_smoke_module_with_image_calls(monkeypatch):
    image_calls = []

    class FakeChainable:
        @classmethod
        def from_name(cls, *args, **kwargs):
            image_calls.append(("from_name", args, kwargs))
            return cls()

        @classmethod
        def from_registry(cls, *args, **kwargs):
            image_calls.append(("from_registry", args, kwargs))
            return cls()

        def entrypoint(self, *args, **kwargs):
            image_calls.append(("entrypoint", args, kwargs))
            return self

        def pip_install(self, *args, **kwargs):
            image_calls.append(("pip_install", args, kwargs))
            return self

        def env(self, *args, **kwargs):
            image_calls.append(("env", args, kwargs))
            return self

        def add_local_file(self, *args, **kwargs):
            image_calls.append(("add_local_file", args, kwargs))
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
    module = importlib.import_module("scripts.qwen_sglang_outlines_smoke")
    return module, image_calls


def test_probe_chat_completion_retries_transient_http_502(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)

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
    smoke = _load_smoke_module(monkeypatch)

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


def test_smoke_image_bakes_prompt_file_for_remote_warmup(monkeypatch):
    smoke, image_calls = _load_smoke_module_with_image_calls(monkeypatch)

    add_local_file_calls = [
        (args, kwargs) for name, args, kwargs in image_calls if name == "add_local_file"
    ]

    assert smoke.PROMPT_PATH.name == "v1.md"
    assert add_local_file_calls == [
        (
            (smoke.PROMPT_PATH,),
            {
                "remote_path": "/backend/app/prompts/todo_extraction/v1.md",
                "copy": True,
            },
        )
    ]


def test_fixed_model_server_startup_uses_requested_model_name(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)
    captured_cmd = []

    class FakeProcess:
        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured_cmd.append(cmd)
        return FakeProcess()

    monkeypatch.setattr(smoke.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(smoke, "_wait_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(smoke, "_warmup_server", lambda *args, **kwargs: None)

    server = smoke.SERVER_BY_MODEL_NAME["Qwen/Qwen3.5-0.8B"]()
    server.startup()

    assert captured_cmd
    assert "Qwen/Qwen3.5-0.8B" in captured_cmd[0]
    assert "4096" in captured_cmd[0]


def test_configured_server_selects_requested_model_server(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)

    class FakeServerClass:
        pass

    monkeypatch.setattr(
        smoke,
        "SERVER_BY_MODEL_NAME",
        {"Qwen/Qwen3.5-0.8B": FakeServerClass},
    )

    server = smoke._configured_server(
        model_name="Qwen/Qwen3.5-0.8B",
        context_length=4096,
    )

    assert isinstance(server, FakeServerClass)


def test_configured_server_rejects_unsupported_context_length(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)

    with pytest.raises(ValueError, match="context_length"):
        smoke._configured_server(
            model_name="Qwen/Qwen3.5-0.8B",
            context_length=2048,
        )


def test_warmup_server_uses_structured_extraction_payload(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)
    captured: dict[str, object] = {}

    def fake_json_request(
        url, *, payload=None, timeout=30, method="POST", headers=None
    ):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": '{"todos": []}'}}]}

    monkeypatch.setattr(smoke, "_json_request", fake_json_request)
    monkeypatch.setattr(smoke, "_read_prompt", lambda: "prompt")
    monkeypatch.setattr(
        smoke,
        "_build_extraction_input",
        lambda: "Current local datetime: 2026-03-24T09:30:00+00:00",
    )

    smoke._warmup_server("Qwen/Qwen3.5-4B")

    payload = captured["payload"]
    assert payload["model"] == "Qwen/Qwen3.5-4B"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "todo_extraction"
    assert payload["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert payload["messages"][0] == {"role": "system", "content": "prompt"}


def test_warmed_flash_url_uses_structured_extraction_payload(monkeypatch):
    smoke = _load_smoke_module(monkeypatch)
    captured: dict[str, object] = {}

    class FakeExperimentalFlashUrls:
        async def aio(self):
            return ["https://modal.test"]

    class FakeCachedServiceFunction:
        _experimental_get_flash_urls = FakeExperimentalFlashUrls()

    class FakeServer:
        def _cached_service_function(self):
            return FakeCachedServiceFunction()

    def fake_probe_chat_completion(base_url, *, payload, timeout, headers=None):
        captured["base_url"] = base_url
        captured["payload"] = payload
        captured["headers"] = headers
        return {"choices": [{"message": {"content": '{"todos": []}'}}]}

    monkeypatch.setattr(smoke, "_probe_chat_completion", fake_probe_chat_completion)
    monkeypatch.setattr(smoke, "_read_prompt", lambda: "prompt")
    monkeypatch.setattr(
        smoke,
        "_build_extraction_input",
        lambda: "Current local datetime: 2026-03-24T09:30:00+00:00",
    )

    flash_url = asyncio.run(
        smoke._warmed_flash_url(
            FakeServer(),
            model_name="Qwen/Qwen3.5-4B",
            session_id="session-123",
            timeout=30,
        )
    )

    payload = captured["payload"]
    assert flash_url == "https://modal.test"
    assert payload["model"] == "Qwen/Qwen3.5-4B"
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["extra_body"]["chat_template_kwargs"]["enable_thinking"] is False
    assert captured["headers"] == {"Modal-Session-ID": "session-123"}
