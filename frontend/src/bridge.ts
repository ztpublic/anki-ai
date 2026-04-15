const PROTOCOL = "anki-ai.transport.v1";

type JsonObject = Record<string, unknown>;
type EventHandler<T = unknown> = (payload: T) => void;

type TransportErrorPayload = {
  code: string;
  message: string;
  details?: unknown;
};

type TransportSuccessResponse<T> = {
  protocol: typeof PROTOCOL;
  kind: "response";
  id: string;
  ok: true;
  result: T;
};

type TransportFailureResponse = {
  protocol: typeof PROTOCOL;
  kind: "response";
  id: string | null;
  ok: false;
  error: TransportErrorPayload;
};

type TransportResponse<T = unknown> =
  | TransportSuccessResponse<T>
  | TransportFailureResponse;

type TransportEventMessage = {
  protocol: typeof PROTOCOL;
  kind: "event";
  event: string;
  payload: unknown;
};

type CallOptions = {
  timeoutMs?: number;
};

type AnkiAIBridge = {
  call: <T = unknown>(
    method: string,
    params?: JsonObject,
    options?: CallOptions,
  ) => Promise<T>;
  send: <T = unknown>(
    method: string,
    params?: JsonObject,
    options?: CallOptions,
  ) => Promise<T>;
  notify: (method: string, params?: JsonObject) => void;
  on: <T = unknown>(event: string, handler: EventHandler<T>) => () => void;
  receive: (message: unknown) => void;
  lastMessage: unknown;
};

declare global {
  function pycmd(
    command: string,
    callback?: (response: unknown) => void,
  ): false;

  interface Window {
    AnkiAI: AnkiAIBridge;
  }
}

export class BridgeTransportError extends Error {
  code: string;
  details?: unknown;

  constructor(code: string, message: string, details?: unknown) {
    super(message);
    this.name = "BridgeTransportError";
    this.code = code;
    this.details = details;
  }
}

const eventHandlers = new Map<string, Set<EventHandler>>();

function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isTransportErrorPayload(
  value: unknown,
): value is TransportErrorPayload {
  return (
    isObject(value) &&
    typeof value.code === "string" &&
    typeof value.message === "string"
  );
}

function parseTransportResponse<T>(
  value: unknown,
  requestId: string,
): TransportResponse<T> {
  if (!isObject(value)) {
    throw new BridgeTransportError(
      "invalid_response",
      "Bridge response must be an object.",
    );
  }

  if (value.protocol !== PROTOCOL || value.kind !== "response") {
    throw new BridgeTransportError(
      "invalid_response",
      "Bridge response has an unsupported shape.",
    );
  }

  if (value.id !== requestId) {
    throw new BridgeTransportError(
      "response_id_mismatch",
      "Bridge response id did not match the request id.",
      { expected: requestId, received: value.id },
    );
  }

  if (value.ok === true) {
    return value as TransportSuccessResponse<T>;
  }

  if (value.ok === false && isTransportErrorPayload(value.error)) {
    return value as TransportFailureResponse;
  }

  throw new BridgeTransportError(
    "invalid_response",
    "Bridge response is missing a valid result or error payload.",
  );
}

function ensureBridgeAvailable(): void {
  if (typeof pycmd !== "function") {
    throw new BridgeTransportError(
      "bridge_unavailable",
      "Anki bridge is not available.",
    );
  }
}

export function call<T = unknown>(
  method: string,
  params: JsonObject = {},
  options: CallOptions = {},
): Promise<T> {
  try {
    ensureBridgeAvailable();
  } catch (error) {
    return Promise.reject(error);
  }

  const requestId = createRequestId();
  const message = {
    protocol: PROTOCOL,
    kind: "request",
    id: requestId,
    method,
    params,
  };

  return new Promise<T>((resolve, reject) => {
    let timeoutId: number | undefined;
    let settled = false;

    const settle = (callback: () => void) => {
      if (settled) {
        return;
      }

      settled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
      callback();
    };

    if (options.timeoutMs !== undefined) {
      timeoutId = window.setTimeout(() => {
        settle(() => {
          reject(
            new BridgeTransportError(
              "request_timeout",
              `Bridge request timed out: ${method}`,
            ),
          );
        });
      }, options.timeoutMs);
    }

    try {
      pycmd(JSON.stringify(message), (response) => {
        settle(() => {
          try {
            const parsed = parseTransportResponse<T>(response, requestId);
            if (parsed.ok) {
              resolve(parsed.result);
              return;
            }

            reject(
              new BridgeTransportError(
                parsed.error.code,
                parsed.error.message,
                parsed.error.details,
              ),
            );
          } catch (error) {
            reject(error);
          }
        });
      });
    } catch (error) {
      settle(() => {
        reject(error);
      });
    }
  });
}

export function notify(method: string, params: JsonObject = {}): void {
  ensureBridgeAvailable();

  pycmd(
    JSON.stringify({
      protocol: PROTOCOL,
      kind: "notification",
      method,
      params,
    }),
  );
}

export function on<T = unknown>(
  event: string,
  handler: EventHandler<T>,
): () => void {
  const handlers = eventHandlers.get(event) ?? new Set<EventHandler>();
  handlers.add(handler as EventHandler);
  eventHandlers.set(event, handlers);

  return () => {
    handlers.delete(handler as EventHandler);
    if (handlers.size === 0) {
      eventHandlers.delete(event);
    }
  };
}

export function receive(message: unknown): void {
  window.AnkiAI.lastMessage = message;

  if (!isObject(message)) {
    return;
  }

  if (
    message.protocol !== PROTOCOL ||
    message.kind !== "event" ||
    typeof message.event !== "string"
  ) {
    return;
  }

  const eventMessage = message as TransportEventMessage;
  const handlers = eventHandlers.get(eventMessage.event);
  if (!handlers) {
    return;
  }

  for (const handler of handlers) {
    try {
      handler(eventMessage.payload);
    } catch (error) {
      console.error("Anki AI bridge event handler failed.", error);
    }
  }
}

export function installBridgeReceiver(): void {
  window.AnkiAI = {
    call,
    send: call,
    notify,
    on,
    receive,
    lastMessage: null,
  };
}
