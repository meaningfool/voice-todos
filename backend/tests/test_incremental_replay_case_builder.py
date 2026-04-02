from evals.incremental_extraction_quality.replay_case_builder import build_replay_steps


def test_replay_case_builder_returns_ordered_transcript_snapshots():
    replay_steps = build_replay_steps(
        [
            "Buy milk",
            "Buy milk",
            "Buy milk and eggs",
            "Buy milk and eggs",
        ],
        final_transcript="Buy milk and eggs",
    )

    assert replay_steps == [
        "Buy milk",
        "Buy milk and eggs",
    ]


def test_replay_case_builder_appends_final_transcript_once():
    replay_steps = build_replay_steps(
        [
            "Buy milk",
            "Buy milk",
        ],
        final_transcript="Buy milk and eggs",
    )

    assert replay_steps == [
        "Buy milk",
        "Buy milk and eggs",
    ]
