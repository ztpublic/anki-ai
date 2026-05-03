import React, { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";

import {
  RegenerationSuggestionPanel,
  type RegenerationMode,
  type SuggestedReplacement,
} from "./RegenerationSuggestionPanel";
import "./styles.css";

const MESSAGE_PREFIX = "anki-ai-reviewer:";
const MOUNT_SELECTOR = "[data-anki-ai-reviewer-regeneration]";

type ReviewerPycmdPayload =
  | {
      action: "regenerate";
      requestId: string;
      cardId: string;
      mode: RegenerationMode;
    }
  | {
      action: "accept";
      requestId: string;
      cardId: string;
      mode: RegenerationMode;
      answer: string;
    };

type ReviewerResultPayload = {
  action: "regenerationResult" | "acceptResult";
  requestId: string;
  cardId: string;
  ok: boolean;
  fields?: {
    answer: string;
  };
  error?: string;
};

type ReviewerPanelEvent = CustomEvent<ReviewerResultPayload>;

declare global {
  function pycmd(command: string, callback?: (response: unknown) => void): false;

  interface Window {
    AnkiAIReviewer?: {
      mountAll: () => void;
      receive: (payload: ReviewerResultPayload) => void;
    };
  }
}

const mountedRoots = new WeakMap<Element, Root>();

function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function postToReviewer(payload: ReviewerPycmdPayload): void {
  pycmd(`${MESSAGE_PREFIX}${JSON.stringify(payload)}`);
}

function reviewerErrorMessage(value: unknown): string {
  if (value instanceof Error) {
    return value.message;
  }

  return "Answer could not be regenerated.";
}

function ReviewerRegenerationPanel({
  cardId,
}: {
  cardId: string;
}) {
  const [suggestion, setSuggestion] = useState<SuggestedReplacement | null>(
    null,
  );
  const activeRequestIdRef = useRef<string | null>(null);
  const activeSuggestion =
    suggestion?.cardId === cardId ? suggestion : null;
  const isRegenerating = activeSuggestion?.status === "loading";

  useEffect(() => {
    const handleResult = (event: Event) => {
      const payload = (event as ReviewerPanelEvent).detail;
      if (
        payload.cardId !== cardId ||
        payload.requestId !== activeRequestIdRef.current
      ) {
        return;
      }

      if (payload.action === "acceptResult") {
        if (payload.ok) {
          setSuggestion(null);
          activeRequestIdRef.current = null;
          return;
        }

        setSuggestion((previousSuggestion) => ({
          cardId,
          mode: previousSuggestion?.mode ?? "answer",
          status: "error",
          error: payload.error ?? "Suggestion could not be accepted.",
        }));
        activeRequestIdRef.current = null;
        return;
      }

      if (!payload.ok || !payload.fields) {
        setSuggestion((previousSuggestion) => ({
          cardId,
          mode: previousSuggestion?.mode ?? "answer",
          status: "error",
          error: payload.error ?? "Answer could not be regenerated.",
        }));
        activeRequestIdRef.current = null;
        return;
      }

      setSuggestion((previousSuggestion) => ({
        cardId,
        mode: previousSuggestion?.mode ?? "answer",
        status: "ready",
        answer: payload.fields?.answer,
      }));
      activeRequestIdRef.current = null;
    };

    window.addEventListener("anki-ai-reviewer-result", handleResult);
    return () => {
      window.removeEventListener("anki-ai-reviewer-result", handleResult);
    };
  }, [cardId]);

  const regenerate = (mode: RegenerationMode) => {
    const requestId = createRequestId();
    activeRequestIdRef.current = requestId;
    setSuggestion({
      cardId,
      mode,
      status: "loading",
    });

    try {
      postToReviewer({
        action: "regenerate",
        requestId,
        cardId,
        mode,
      });
    } catch (error) {
      activeRequestIdRef.current = null;
      setSuggestion({
        cardId,
        mode,
        status: "error",
        error: reviewerErrorMessage(error),
      });
    }
  };

  const accept = () => {
    if (
      activeSuggestion?.status !== "ready" ||
      activeSuggestion.answer === undefined
    ) {
      return;
    }

    const requestId = createRequestId();
    activeRequestIdRef.current = requestId;

    try {
      postToReviewer({
        action: "accept",
        requestId,
        cardId,
        mode: activeSuggestion.mode,
        answer: activeSuggestion.answer,
      });
      setSuggestion({
        ...activeSuggestion,
        status: "loading",
      });
    } catch (error) {
      activeRequestIdRef.current = null;
      setSuggestion({
        cardId,
        mode: activeSuggestion.mode,
        status: "error",
        error: reviewerErrorMessage(error),
      });
    }
  };

  const discard = () => {
    activeRequestIdRef.current = null;
    setSuggestion(null);
  };

  return (
    <RegenerationSuggestionPanel
      activeSuggestion={activeSuggestion}
      isRegenerating={isRegenerating}
      onRegenerate={regenerate}
      onAccept={accept}
      onDiscard={discard}
      className="anki-ai-reviewer-panel mt-4 rounded-md border border-zinc-200"
    />
  );
}

function mountAll(): void {
  document.querySelectorAll<HTMLElement>(MOUNT_SELECTOR).forEach((element) => {
    if (mountedRoots.has(element)) {
      return;
    }

    const cardId = element.dataset.cardId;
    if (!cardId) {
      return;
    }

    const root = createRoot(element);
    mountedRoots.set(element, root);
    root.render(
      <React.StrictMode>
        <ReviewerRegenerationPanel cardId={cardId} />
      </React.StrictMode>,
    );
  });
}

function receive(payload: ReviewerResultPayload): void {
  window.dispatchEvent(
    new CustomEvent("anki-ai-reviewer-result", {
      detail: payload,
    }),
  );
}

window.AnkiAIReviewer = {
  mountAll,
  receive,
};

const observer = new MutationObserver(() => {
  mountAll();
});

if (document.body) {
  observer.observe(document.body, { childList: true, subtree: true });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountAll, { once: true });
} else {
  mountAll();
}
