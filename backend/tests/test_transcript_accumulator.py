from app.transcript_accumulator import TranscriptAccumulator


class TestApplyEvent:
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
        assert accumulator.full_text == "buy milk "
