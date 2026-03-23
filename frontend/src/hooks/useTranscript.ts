import { useCallback, useRef, useState } from "react";
import type { Todo } from "../types";

export type Status = "idle" | "connecting" | "recording" | "extracting";

interface Token {
  text: string;
  is_final: boolean;
}

interface TranscriptMessage {
  type: "started" | "transcript" | "todos" | "stopped" | "error";
  tokens?: Token[];
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

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const stopTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const start = useCallback(async () => {
    // Fix #5: Guard against double-start
    if (status !== "idle") return;

    setStatus("connecting");
    setFinalText("");
    setInterimText("");
    setTodos([]);

    try {
      // Open WebSocket to backend
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
      wsRef.current = ws;

      // Fix #1: Wait for open/error using Promise, then set persistent handlers after
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
      });

      // Fix #1: Set persistent handlers after the connection is established
      ws.onmessage = (event) => {
        const msg: TranscriptMessage = JSON.parse(event.data);

        if (msg.type === "started") {
          setStatus("recording");
        } else if (msg.type === "transcript" && msg.tokens) {
          let newFinal = "";
          let newInterim = "";
          for (const token of msg.tokens) {
            if (token.is_final) {
              newFinal += token.text;
            } else {
              newInterim += token.text;
            }
          }
          if (newFinal) {
            setFinalText((prev) => prev + newFinal);
          }
          setInterimText(newInterim);
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
          if (stopTimeoutRef.current !== null) {
            clearTimeout(stopTimeoutRef.current);
            stopTimeoutRef.current = null;
          }
          setStatus("idle");
          setInterimText("");
          cleanup();
        } else if (msg.type === "error") {
          console.error("Server error:", msg.message);
          setStatus("idle");
          cleanup();
        }
      };

      ws.onerror = () => {
        setStatus("idle");
        cleanup();
      };

      // Fix #3: onclose only updates status; cleanup() already handles closing
      ws.onclose = () => {
        setStatus("idle");
      };

      // Start mic capture
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      mediaStreamRef.current = stream;

      // Set up AudioWorklet for PCM extraction
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

      // Fix #4: Don't connect workletNode to destination (avoids mic echo)
      source.connect(workletNode);

      // Tell server to start Soniox session
      ws.send(JSON.stringify({ type: "start" }));
    } catch (err) {
      console.error("Failed to start:", err);
      setStatus("idle");
      cleanup();
    }
  }, [status]);

  const stop = useCallback(() => {
    setStatus("extracting");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));

      // Fix #2: Timeout in case server never responds with "stopped"
      stopTimeoutRef.current = setTimeout(() => {
        stopTimeoutRef.current = null;
        cleanup();
        setStatus("idle");
      }, 5000);
    }
    // Stop mic immediately
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
  }, []);

  function cleanup() {
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
    // Fix #3: Only close WebSocket if it isn't already closed/closing
    if (
      wsRef.current &&
      wsRef.current.readyState !== WebSocket.CLOSED &&
      wsRef.current.readyState !== WebSocket.CLOSING
    ) {
      wsRef.current.close();
    }
    wsRef.current = null;
  }

  return { status, finalText, interimText, todos, start, stop };
}
