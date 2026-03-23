/**
 * Pure transcript accumulation logic, extracted from useTranscript
 * for testability. Processes the same message sequence the WebSocket
 * handler receives and produces the final display state.
 */

interface Token {
  text: string;
  is_final: boolean;
}

interface TranscriptMessage {
  type: "started" | "transcript" | "todos" | "stopped" | "error";
  transcript?: string;
  tokens?: Token[];
  items?: unknown[];
  message?: string;
}

export interface TranscriptState {
  finalText: string;
  interimText: string;
}

/**
 * Process a sequence of messages and return the final display state.
 * Mirrors the onmessage handler in useTranscript.
 *
 * @param useBackendTranscript - when true, uses the backend's transcript
 *   field from the stopped message (the fix). When false, uses the old
 *   behavior of promoting interimTextRef (the bug).
 */
export function processMessages(
  messages: TranscriptMessage[],
  useBackendTranscript = true
): TranscriptState {
  let finalText = "";
  let interimText = "";
  // Mirrors interimTextRef.current
  let interimRef = "";

  for (const msg of messages) {
    if (msg.type === "transcript" && msg.tokens) {
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
        finalText += newFinal;
      }
      interimText = newInterim;
      interimRef = newInterim;
    } else if (msg.type === "stopped") {
      if (useBackendTranscript && msg.transcript) {
        finalText = msg.transcript;
      } else if (interimRef) {
        finalText += interimRef;
      }
      interimRef = "";
      interimText = "";
    }
  }

  return { finalText, interimText };
}
