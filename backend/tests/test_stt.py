from app.stt import BoundaryState, SttEvent, SttToken


def test_boundary_state_distinguishes_unsupported_from_not_observed():
    assert BoundaryState.UNSUPPORTED != BoundaryState.NOT_OBSERVED

    event = SttEvent(
        tokens=[SttToken(text="hello ", is_final=True)],
        finalization_state=BoundaryState.UNSUPPORTED,
        endpoint_state=BoundaryState.NOT_OBSERVED,
    )

    assert event.finalization_state is BoundaryState.UNSUPPORTED
    assert event.endpoint_state is BoundaryState.NOT_OBSERVED
