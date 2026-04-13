import { useCallback, useEffect, useRef, useState } from "react";
import type { Todo } from "../types";
import {
  applyTranscriptTokens,
  EMPTY_TRANSCRIPT_STATE,
  finalizeTranscript,
} from "./transcriptReducer";

export type Status = "idle" | "connecting" | "recording" | "extracting";

interface Token {
  text: string;
  is_final: boolean;
}

interface TranscriptMessage {
  type: "started" | "transcript" | "todos" | "stopped" | "error";
  transcript?: string;
  tokens?: Token[];
  warning?: string;
  items?: Array<{
    text: string;
    priority?: string;
    category?: string;
    due_date?: string;
    notification?: string;
    assign_to?: string;
  }>;
  message?: string;
}

export function useTranscript() {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");
  const [todos, setTodos] = useState<Todo[]>([]);
  const [micRecordingUrl, setMicRecordingUrl] = useState<string | null>(null);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  const transcriptStateRef = useRef(EMPTY_TRANSCRIPT_STATE);
  const micRecordingUrlRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const stopTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const micTailTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const micChunksRef = useRef<Blob[]>([]);

  const updateTranscriptState = useCallback((nextState: typeof EMPTY_TRANSCRIPT_STATE) => {
    transcriptStateRef.current = nextState;
    setFinalText(nextState.finalText);
    setInterimText(nextState.interimText);
  }, []);

  const clearMicRecordingUrl = useCallback(() => {
    if (micRecordingUrlRef.current) {
      URL.revokeObjectURL(micRecordingUrlRef.current);
      micRecordingUrlRef.current = null;
    }
    setMicRecordingUrl(null);
  }, []);

  const cleanup = useCallback(
    ({ revokeRecordingUrl = false }: { revokeRecordingUrl?: boolean } = {}) => {
      if (micTailTimeoutRef.current !== null) {
        clearTimeout(micTailTimeoutRef.current);
        micTailTimeoutRef.current = null;
      }
      if (stopTimeoutRef.current !== null) {
        clearTimeout(stopTimeoutRef.current);
        stopTimeoutRef.current = null;
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        if (revokeRecordingUrl) {
          mediaRecorderRef.current.onstop = null;
        }
        mediaRecorderRef.current.stop();
      }
      mediaRecorderRef.current = null;
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      if (workletNodeRef.current) {
        workletNodeRef.current.disconnect();
        workletNodeRef.current = null;
      }
      if (audioContextRef.current) {
        void audioContextRef.current.close();
        audioContextRef.current = null;
      }
      if (
        wsRef.current &&
        wsRef.current.readyState !== WebSocket.CLOSED &&
        wsRef.current.readyState !== WebSocket.CLOSING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
      if (revokeRecordingUrl) {
        clearMicRecordingUrl();
      }
    },
    [clearMicRecordingUrl]
  );

  useEffect(() => {
    return () => cleanup({ revokeRecordingUrl: true });
  }, [cleanup]);

  const start = useCallback(async () => {
    if (status !== "idle") return;

    setStatus("connecting");
    setWarningMessage(null);
    updateTranscriptState(EMPTY_TRANSCRIPT_STATE);
    setTodos([]);
    clearMicRecordingUrl();

    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
      wsRef.current = ws;

      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => {
          resolve();
        };
        ws.onerror = () => {
          reject(new Error("WebSocket connection failed"));
        };
      });

      ws.onmessage = (event) => {
        const msg: TranscriptMessage = JSON.parse(event.data);

        if (msg.type === "started") {
          setStatus("recording");
        } else if (msg.type === "transcript" && msg.tokens) {
          updateTranscriptState(
            applyTranscriptTokens(transcriptStateRef.current, msg.tokens)
          );
        } else if (msg.type === "todos" && msg.items) {
          setTodos(
            msg.items.map((item) => ({
              text: item.text,
              priority: item.priority as Todo["priority"],
              category: item.category,
              dueDate: item.due_date,
              notification: item.notification,
              assignTo: item.assign_to,
            }))
          );
        } else if (msg.type === "stopped") {
          updateTranscriptState(
            finalizeTranscript(transcriptStateRef.current, msg.transcript)
          );
          setWarningMessage(msg.warning ?? null);
          setStatus("idle");
          cleanup();
        } else if (msg.type === "error") {
          console.error("Server error:", msg.message);
          setWarningMessage(msg.message ?? "Something went wrong.");
          setStatus("idle");
          cleanup();
        }
      };

      ws.onerror = () => {
        setWarningMessage("WebSocket connection failed.");
        setStatus("idle");
        cleanup();
      };

      ws.onclose = () => {
        setStatus("idle");
      };

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      micChunksRef.current = [];
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) micChunksRef.current.push(e.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(micChunksRef.current, { type: mediaRecorder.mimeType });
        const nextUrl = URL.createObjectURL(blob);
        if (micRecordingUrlRef.current) {
          URL.revokeObjectURL(micRecordingUrlRef.current);
        }
        micRecordingUrlRef.current = nextUrl;
        setMicRecordingUrl(nextUrl);
      };
      mediaRecorder.start();

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      await audioContext.audioWorklet.addModule("/pcm-worklet.js");
      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, "pcm-processor");
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(event.data);
        }
      };

      source.connect(workletNode);

      ws.send(JSON.stringify({ type: "start" }));
    } catch (err) {
      console.error("Failed to start:", err);
      setWarningMessage("Microphone setup failed.");
      setStatus("idle");
      cleanup();
    }
  }, [clearMicRecordingUrl, cleanup, status, updateTranscriptState]);

  const stop = useCallback(() => {
    if (status !== "recording") return;

    setStatus("extracting");
    setWarningMessage(null);

    const MIC_TAIL_MS = 200;

    const teardownAndStop = () => {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
        mediaRecorderRef.current = null;
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((t) => t.stop());
        mediaStreamRef.current = null;
      }
      if (workletNodeRef.current) {
        workletNodeRef.current.disconnect();
        workletNodeRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
        audioContextRef.current = null;
      }

      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "stop" }));

        stopTimeoutRef.current = setTimeout(() => {
          setWarningMessage("Timed out waiting for the backend to stop.");
          cleanup();
          setStatus("idle");
        }, 30000);
      }
    };

    micTailTimeoutRef.current = setTimeout(teardownAndStop, MIC_TAIL_MS);
  }, [cleanup, status]);

  return {
    status,
    finalText,
    interimText,
    todos,
    micRecordingUrl,
    warningMessage,
    start,
    stop,
  };
}
