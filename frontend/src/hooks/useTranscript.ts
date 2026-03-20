import { useCallback, useRef, useState } from "react";

export type Status = "idle" | "connecting" | "recording" | "stopping";

interface Token {
  text: string;
  is_final: boolean;
}

interface TranscriptMessage {
  type: "started" | "transcript" | "stopped" | "error";
  tokens?: Token[];
  message?: string;
}

export function useTranscript() {
  const [status, setStatus] = useState<Status>("idle");
  const [finalText, setFinalText] = useState("");
  const [interimText, setInterimText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  const start = useCallback(async () => {
    setStatus("connecting");
    setFinalText("");
    setInterimText("");

    try {
      // Open WebSocket to backend
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
      wsRef.current = ws;

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
        } else if (msg.type === "stopped") {
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

      ws.onclose = () => {
        setStatus("idle");
        cleanup();
      };

      // Wait for WebSocket to open
      await new Promise<void>((resolve, reject) => {
        ws.onopen = () => resolve();
        ws.onerror = () => reject(new Error("WebSocket connection failed"));
      });

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

      source.connect(workletNode);
      workletNode.connect(audioContext.destination);

      // Tell server to start Soniox session
      ws.send(JSON.stringify({ type: "start" }));
    } catch (err) {
      console.error("Failed to start:", err);
      setStatus("idle");
      cleanup();
    }
  }, []);

  const stop = useCallback(() => {
    setStatus("stopping");
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "stop" }));
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
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }

  return { status, finalText, interimText, start, stop };
}
