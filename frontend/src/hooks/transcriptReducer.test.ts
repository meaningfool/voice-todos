import { describe, it, expect } from "vitest";
import {
  applyTranscriptTokens,
  EMPTY_TRANSCRIPT_STATE,
  finalizeTranscript,
  processMessages,
} from "./transcriptReducer";

describe("transcriptReducer", () => {
  it("accumulates final text while replacing interim text", () => {
    const nextState = applyTranscriptTokens(EMPTY_TRANSCRIPT_STATE, [
      { text: "hello ", is_final: true },
      { text: "world", is_final: false },
    ]);

    expect(nextState).toEqual({
      finalText: "hello ",
      interimText: "world",
    });
  });

  it("uses the backend transcript as the source of truth when stopping", () => {
    const state = {
      finalText: "hello ",
      interimText: "world",
    };

    expect(finalizeTranscript(state, "hello world")).toEqual({
      finalText: "hello world",
      interimText: "",
    });
  });

  it("falls back to the accumulated interim tail when stopped without a transcript", () => {
    const state = {
      finalText: "hello ",
      interimText: "world",
    };

    expect(finalizeTranscript(state)).toEqual({
      finalText: "hello world",
      interimText: "",
    });
  });

  it("replays the same message flow the hook consumes", () => {
    const messages = [
      {
        type: "transcript" as const,
        tokens: [
          { text: "hello ", is_final: true },
          { text: "world", is_final: false },
        ],
      },
      { type: "todos" as const, items: [] },
      { type: "stopped" as const, transcript: "hello world" },
    ];

    expect(processMessages(messages)).toEqual({
      finalText: "hello world",
      interimText: "",
    });
  });
});
