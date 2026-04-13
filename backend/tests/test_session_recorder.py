import json

import app.session_recorder as session_recorder_module
from app.session_recorder import SessionRecorder


def test_session_recorder_writes_expected_soniox_files(tmp_path, monkeypatch):
    monkeypatch.setattr(session_recorder_module, "SESSIONS_DIR", tmp_path / "recent")

    recorder = SessionRecorder()
    recorder.start()
    recorder.write_audio(b"\x00\x01")
    recorder.write_soniox_message('{"tokens": [{"text": "hello ", "is_final": true}]}')
    recorder.write_result("hello ", [{"text": "Hello"}])
    recorder.stop()

    session_dirs = list((tmp_path / "recent").iterdir())
    assert len(session_dirs) == 1
    session_dir = session_dirs[0]

    assert (session_dir / "audio.pcm").read_bytes() == b"\x00\x01"
    assert (session_dir / "soniox.jsonl").read_text(encoding="utf-8").splitlines() == [
        '{"tokens": [{"text": "hello ", "is_final": true}]}'
    ]
    assert json.loads((session_dir / "result.json").read_text(encoding="utf-8")) == {
        "transcript": "hello ",
        "todos": [{"text": "Hello"}],
    }
