from app.stt import BoundaryState
from app.stt_soniox import build_soniox_config, translate_soniox_event


def test_build_soniox_config_matches_current_production_defaults():
    config = build_soniox_config("soniox-test-key")

    assert config["api_key"] == "soniox-test-key"
    assert config["model"] == "stt-rt-v4"
    assert config["audio_format"] == "pcm_s16le"
    assert config["sample_rate"] == 16000
    assert config["num_channels"] == 1
    assert config["enable_endpoint_detection"] is True
    assert config["max_endpoint_delay_ms"] == 1000


def test_translate_soniox_event_sets_fin_and_endpoint_flags():
    event = translate_soniox_event(
        {
            "tokens": [
                {"text": "hello ", "is_final": True},
                {"text": "<end>", "is_final": True},
                {"text": "<fin>", "is_final": True},
            ]
        }
    )

    assert [token.text for token in event.tokens] == ["hello "]
    assert event.finalization_state is BoundaryState.OBSERVED
    assert event.endpoint_state is BoundaryState.OBSERVED
    assert event.is_finished is False
