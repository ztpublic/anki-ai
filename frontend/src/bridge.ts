type BridgeResponse = unknown;

declare global {
  function pycmd(command: string, callback?: (response: BridgeResponse) => void): false;

  interface Window {
    AnkiAI: {
      send: (type: string, payload?: Record<string, unknown>) => Promise<BridgeResponse>;
      receive: (message: unknown) => void;
      lastMessage: unknown;
    };
  }
}

export function send(
  type: string,
  payload: Record<string, unknown> = {},
): Promise<BridgeResponse> {
  if (typeof pycmd !== "function") {
    return Promise.reject(new Error("Anki bridge is not available."));
  }

  return new Promise((resolve) => {
    pycmd(JSON.stringify({ type, payload }), resolve);
  });
}

export function installBridgeReceiver(): void {
  window.AnkiAI = {
    send,
    receive(message: unknown) {
      window.AnkiAI.lastMessage = message;
    },
    lastMessage: null,
  };
}
