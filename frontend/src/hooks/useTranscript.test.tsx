import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTranscript } from "./useTranscript";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.CONNECTING;
  sent: unknown[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  });

  constructor(public readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  send(data: unknown) {
    this.sent.push(data);
  }

  triggerOpen() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  emitMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

class MockMediaRecorder {
  static instances: MockMediaRecorder[] = [];

  mimeType = "audio/webm";
  state: "inactive" | "recording" = "inactive";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(stream: MediaStream) {
    void stream;
    MockMediaRecorder.instances.push(this);
  }

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
}

class MockAudioWorkletNode {
  port = { onmessage: null as ((event: { data: ArrayBuffer }) => void) | null };
  disconnect = vi.fn();

  constructor(audioContext: AudioContext, name: string) {
    void audioContext;
    void name;
  }
}

describe("useTranscript", () => {
  const trackStop = vi.fn();
  const stream = {
    getTracks: () => [{ stop: trackStop }],
  } as unknown as MediaStream;
  const addModule = vi.fn().mockResolvedValue(undefined);
  const sourceConnect = vi.fn();
  const createMediaStreamSource = vi.fn(() => ({ connect: sourceConnect }));
  const closeAudioContext = vi.fn().mockResolvedValue(undefined);
  const createObjectURL = vi.fn();
  const revokeObjectURL = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    MockMediaRecorder.instances = [];
    trackStop.mockClear();
    addModule.mockClear();
    createMediaStreamSource.mockClear();
    closeAudioContext.mockClear();
    sourceConnect.mockClear();
    createObjectURL.mockReset();
    createObjectURL
      .mockReturnValueOnce("blob:first")
      .mockReturnValueOnce("blob:second");
    revokeObjectURL.mockReset();

    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.stubGlobal("MediaRecorder", MockMediaRecorder);
    vi.stubGlobal("AudioWorkletNode", MockAudioWorkletNode);
    vi.stubGlobal(
      "AudioContext",
      class {
        audioWorklet = { addModule };
        createMediaStreamSource = createMediaStreamSource;
        close = closeAudioContext;

        constructor(options: unknown) {
          void options;
        }
      }
    );

    Object.defineProperty(globalThis.navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue(stream),
      },
    });

    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  type HookResult = ReturnType<typeof renderHook<typeof useTranscript>>["result"];

  async function startRecording(result: HookResult) {
    await act(async () => {
      const promise = result.current.start();
      const ws = MockWebSocket.instances.at(-1);
      if (!ws) {
        throw new Error("WebSocket was not created");
      }
      ws.triggerOpen();
      await promise;
    });

    const ws = MockWebSocket.instances.at(-1);
    if (!ws) {
      throw new Error("WebSocket was not created");
    }

    act(() => {
      ws.emitMessage({ type: "started" });
    });
    expect(result.current.status).toBe("recording");

    return ws;
  }

  async function stopRecording(
    result: HookResult,
    ws: MockWebSocket,
    transcript: string
  ) {
    await act(async () => {
      result.current.stop();
      vi.advanceTimersByTime(200);
    });

    act(() => {
      ws.emitMessage({ type: "todos", items: [] });
      ws.emitMessage({ type: "stopped", transcript });
    });
    expect(result.current.status).toBe("idle");
  }

  it("revokes the previous microphone recording URL before starting again", async () => {
    const { result } = renderHook(() => useTranscript());

    const firstSocket = await startRecording(result);
    await stopRecording(result, firstSocket, "first transcript");
    expect(result.current.micRecordingUrl).toBe("blob:first");

    await startRecording(result);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:first");
  });

  it("cleans up live browser resources on unmount", async () => {
    const { result, unmount } = renderHook(() => useTranscript());
    const ws = await startRecording(result);

    unmount();

    expect(trackStop).toHaveBeenCalledTimes(1);
    expect(ws.close).toHaveBeenCalledTimes(1);
    expect(closeAudioContext).toHaveBeenCalledTimes(1);
  });

  it("surfaces backend warnings after stop", async () => {
    const { result } = renderHook(() => useTranscript());
    const ws = await startRecording(result);

    await act(async () => {
      result.current.stop();
      vi.advanceTimersByTime(200);
    });

    act(() => {
      ws.emitMessage({ type: "todos", items: [] });
      ws.emitMessage({
        type: "stopped",
        transcript: "partial transcript",
        warning: "Timed out waiting for the final transcript.",
      });
    });
    expect(result.current.warningMessage).toBe(
      "Timed out waiting for the final transcript."
    );
  });
});
