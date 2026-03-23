import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useTranscript } from "./useTranscript";

/**
 * Test the stop sequence: audio pipeline must flush before the
 * "stop" message is sent to the backend.
 *
 * The correct order is:
 *   1. Stop mic (immediate)
 *   2. Wait 300ms for buffered audio to flush
 *   3. Disconnect worklet + close audio context
 *   4. Send {"type":"stop"} to backend
 *
 * If stop is sent before the flush, the last words are lost.
 */

// Track call order
const callOrder: string[] = [];

// Mock WebSocket that auto-resolves onopen and simulates "started"
const mockWsSend = vi.fn((data: unknown) => {
  if (typeof data === "string") {
    const parsed = JSON.parse(data);
    callOrder.push(`ws.send:${parsed.type}`);
  }
});

let capturedOnMessage: ((event: { data: string }) => void) | null = null;

class MockWebSocket {
  static readonly OPEN = 1;
  static readonly CLOSED = 3;
  static readonly CLOSING = 2;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send = mockWsSend;
  close() {
    this.readyState = MockWebSocket.CLOSED;
  }

  constructor() {
    // Auto-fire onopen on next microtask so the Promise resolves
    queueMicrotask(() => {
      this.onopen?.();
      // After onopen, the hook sets onmessage. Capture it and send "started".
      queueMicrotask(() => {
        capturedOnMessage = this.onmessage;
        this.onmessage?.({ data: JSON.stringify({ type: "started" }) });
      });
    });
  }
}

const mockTrackStop = vi.fn(() => callOrder.push("mic.stop"));
const mockWorkletDisconnect = vi.fn(() => callOrder.push("worklet.disconnect"));
const mockAudioContextClose = vi.fn(() =>
  callOrder.push("audioContext.close")
);

describe("useTranscript stop sequence", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    callOrder.length = 0;
    mockWsSend.mockClear();
    mockTrackStop.mockClear();
    mockWorkletDisconnect.mockClear();
    mockAudioContextClose.mockClear();
    capturedOnMessage = null;

    vi.stubGlobal("WebSocket", MockWebSocket);
    // Must use a real class (not vi.fn()) so `new AudioContext()` works
    vi.stubGlobal(
      "AudioContext",
      class MockAudioContext {
        close = mockAudioContextClose;
        audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
        createMediaStreamSource = vi
          .fn()
          .mockReturnValue({ connect: vi.fn() });
      }
    );
    vi.stubGlobal("navigator", {
      mediaDevices: {
        getUserMedia: vi.fn().mockResolvedValue({
          getTracks: () => [{ stop: mockTrackStop }],
        }),
      },
    });
    vi.stubGlobal(
      "AudioWorkletNode",
      class MockAudioWorkletNode {
        disconnect = mockWorkletDisconnect;
        port = { onmessage: null };
      }
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("sends stop message AFTER flush delay, not synchronously", async () => {
    const { result } = renderHook(() => useTranscript());

    // Start a session — mock WebSocket auto-connects and sends "started"
    await act(async () => {
      await result.current.start();
      // Flush microtasks so onopen and onmessage("started") fire
      await vi.advanceTimersByTimeAsync(0);
    });

    // Should now be in "recording" state
    expect(result.current.status).toBe("recording");

    // Clear tracking before stop
    callOrder.length = 0;

    // Call stop
    act(() => {
      result.current.stop();
    });

    // IMMEDIATELY after stop: mic should be stopped
    expect(callOrder).toContain("mic.stop");
    // But stop message must NOT have been sent yet
    expect(callOrder).not.toContain("ws.send:stop");

    // Advance past the 300ms flush delay
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // NOW the stop message should be sent
    expect(callOrder).toContain("ws.send:stop");

    // Verify full order: mic.stop → worklet.disconnect → audioContext.close → ws.send:stop
    const micIdx = callOrder.indexOf("mic.stop");
    const workletIdx = callOrder.indexOf("worklet.disconnect");
    const audioCtxIdx = callOrder.indexOf("audioContext.close");
    const stopIdx = callOrder.indexOf("ws.send:stop");

    expect(micIdx).toBeLessThan(workletIdx);
    expect(workletIdx).toBeLessThan(audioCtxIdx);
    expect(audioCtxIdx).toBeLessThan(stopIdx);
  });
});
