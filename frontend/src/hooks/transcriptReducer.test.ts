import { describe, it, expect } from "vitest";
import { processMessages } from "./transcriptReducer";

describe("processMessages — backend transcript as source of truth", () => {
  // Reproduces the real bug: a transcript message with only finals
  // clears interimRef, so the old promotion logic loses the tail.
  const messages = [
    {
      type: "transcript" as const,
      tokens: [
        { text: "hello ", is_final: false },
        { text: "world", is_final: false },
      ],
    },
    // Finals-only message clears interimRef to ""
    {
      type: "transcript" as const,
      tokens: [{ text: "hello ", is_final: true }],
    },
    { type: "todos" as const, items: [] },
  ];

  it("loses interim tail without backend transcript", () => {
    const result = processMessages(
      [...messages, { type: "stopped" as const }],
      false
    );
    expect(result.finalText).toBe("hello ");
    expect(result.finalText).not.toContain("world");
  });

  it("preserves full transcript with backend transcript", () => {
    const result = processMessages(
      [...messages, { type: "stopped" as const, transcript: "hello world" }],
      true
    );
    expect(result.finalText).toBe("hello world");
  });
});
