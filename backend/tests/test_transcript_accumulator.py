from app.stt import BoundaryState, SttEvent, SttToken
from app.transcript_accumulator import TranscriptAccumulator


class TestApplyEvent:
    def test_stable_text_matches_final_parts(self):
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "hello ", "is_final": True}]})
        accumulator.apply_event({"tokens": [{"text": "world", "is_final": True}]})

        assert accumulator.stable_text == "hello world"
        assert accumulator.provisional_text == ""
        assert accumulator.full_text == "hello world"

    def test_provisional_text_matches_interim_parts(self):
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "hello", "is_final": False}]})

        assert accumulator.stable_text == ""
        assert accumulator.provisional_text == "hello"
        assert accumulator.full_text == "hello"

    def test_stable_and_provisional_text_compose_full_text(self):
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "hello ", "is_final": True}]})
        accumulator.apply_event({"tokens": [{"text": "wor", "is_final": False}]})

        assert accumulator.stable_text == "hello "
        assert accumulator.provisional_text == "wor"
        assert accumulator.full_text == "hello wor"

    def test_end_token_is_detected(self):
        """apply_event returns has_endpoint=True when <end> token is present."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_event(
            {
                "tokens": [
                    {"text": "hello ", "is_final": True},
                    {"text": "<end>", "is_final": True},
                ]
            }
        )

        assert result.has_endpoint is True

    def test_end_token_is_filtered_from_tokens(self):
        """<end> token does not appear in the returned token list."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_event(
            {
                "tokens": [
                    {"text": "hello ", "is_final": True},
                    {"text": "<end>", "is_final": True},
                ]
            }
        )

        assert all(token["text"] != "<end>" for token in result.tokens)

    def test_end_token_is_not_accumulated(self):
        """<end> token text does not end up in the transcript."""
        accumulator = TranscriptAccumulator()

        accumulator.apply_event(
            {
                "tokens": [
                    {"text": "hello ", "is_final": True},
                    {"text": "<end>", "is_final": True},
                ]
            }
        )

        assert accumulator.full_text == "hello "

    def test_no_endpoint_without_end_token(self):
        """Regular tokens do not set has_endpoint."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_event(
            {"tokens": [{"text": "hello ", "is_final": True}]}
        )

        assert result.has_endpoint is False

    def test_final_token_count(self):
        """Result includes count of new final tokens, excluding <end>."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_event(
            {
                "tokens": [
                    {"text": "hello ", "is_final": True},
                    {"text": "world ", "is_final": True},
                    {"text": "<end>", "is_final": True},
                ]
            }
        )

        assert result.final_token_count == 2

    def test_fin_behavior_preserved(self):
        """Existing <fin> handling still works."""
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "interim", "is_final": False}]})
        assert accumulator.interim_parts == ["interim"]

        result = accumulator.apply_event(
            {"tokens": [{"text": "<fin>", "is_final": True}]}
        )

        assert accumulator.interim_parts == []
        assert result.has_endpoint is False

    def test_fin_token_is_reported_without_endpoint(self):
        """<fin> should be surfaced separately from endpoint handling."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_event(
            {"tokens": [{"text": "<fin>", "is_final": True}]}
        )

        assert result.has_fin is True
        assert result.has_endpoint is False
        assert result.final_token_count == 0

    def test_final_tokens_clear_stale_interim_text(self):
        """A later final-only event replaces, rather than appends, stale interim."""
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "buy mi", "is_final": False}]})
        accumulator.apply_event({"tokens": [{"text": "buy milk ", "is_final": True}]})

        assert accumulator.interim_parts == []
        assert accumulator.stable_text == "buy milk "
        assert accumulator.provisional_text == ""
        assert accumulator.full_text == "buy milk "

    def test_identical_stable_replacement_does_not_change_full_text(self):
        accumulator = TranscriptAccumulator()

        accumulator.apply_event({"tokens": [{"text": "buy mi", "is_final": False}]})
        assert accumulator.full_text == "buy mi"

        accumulator.apply_event({"tokens": [{"text": "buy mi", "is_final": True}]})

        assert accumulator.stable_text == "buy mi"
        assert accumulator.provisional_text == ""
        assert accumulator.full_text == "buy mi"

    def test_apply_stt_event_accepts_normalized_provider_events(self):
        """Normalized STT events drive the same accumulator semantics."""
        accumulator = TranscriptAccumulator()

        result = accumulator.apply_stt_event(
            SttEvent(
                tokens=[SttToken(text="hello ", is_final=True)],
                finalization_state=BoundaryState.OBSERVED,
                endpoint_state=BoundaryState.OBSERVED,
            )
        )

        assert accumulator.full_text == "hello "
        assert accumulator.stable_text == "hello "
        assert accumulator.provisional_text == ""
        assert result.has_fin is True
        assert result.has_endpoint is True
        assert result.final_token_count == 1

    def test_apply_stt_event_handles_stable_only_additive_provider_flow(self):
        accumulator = TranscriptAccumulator()

        accumulator.apply_stt_event(
            SttEvent(
                tokens=[SttToken(text="Buy milk", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        )
        accumulator.apply_stt_event(
            SttEvent(
                tokens=[SttToken(text=" tomorrow", is_final=True)],
                finalization_state=BoundaryState.NOT_OBSERVED,
                endpoint_state=BoundaryState.UNSUPPORTED,
            )
        )

        assert accumulator.stable_text == "Buy milk tomorrow"
        assert accumulator.provisional_text == ""
        assert accumulator.full_text == "Buy milk tomorrow"
