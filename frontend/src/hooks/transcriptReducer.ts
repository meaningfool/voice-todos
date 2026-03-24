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

export const EMPTY_TRANSCRIPT_STATE: TranscriptState = {
  finalText: "",
  interimText: "",
};

export function applyTranscriptTokens(
  state: TranscriptState,
  tokens: Token[]
): TranscriptState {
  let newFinal = "";
  let newInterim = "";

  for (const token of tokens) {
    if (token.is_final) {
      newFinal += token.text;
    } else {
      newInterim += token.text;
    }
  }

  return {
    finalText: newFinal ? state.finalText + newFinal : state.finalText,
    interimText: newInterim,
  };
}

export function finalizeTranscript(
  state: TranscriptState,
  transcript?: string
): TranscriptState {
  return {
    finalText: transcript ?? `${state.finalText}${state.interimText}`,
    interimText: "",
  };
}

export function processMessages(messages: TranscriptMessage[]): TranscriptState {
  let state = EMPTY_TRANSCRIPT_STATE;

  for (const msg of messages) {
    if (msg.type === "transcript" && msg.tokens) {
      state = applyTranscriptTokens(state, msg.tokens);
    } else if (msg.type === "stopped") {
      state = finalizeTranscript(state, msg.transcript);
    }
  }

  return state;
}
