import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";
import { useState } from "react";

export type RegenerationMode = "answer";

export type SuggestedReplacement = {
  cardId: string;
  mode: RegenerationMode;
  status: "loading" | "ready" | "error";
  answer?: string;
  error?: string;
};

type RegenerationSuggestionPanelProps = {
  activeSuggestion: SuggestedReplacement | null;
  isRegenerating: boolean;
  onRegenerate: (mode: RegenerationMode, instructions?: string) => void;
  onAccept: () => void;
  onDiscard: () => void;
  className?: string;
};

export function RegenerationSuggestionPanel({
  activeSuggestion,
  isRegenerating,
  onRegenerate,
  onAccept,
  onDiscard,
  className = "",
}: RegenerationSuggestionPanelProps) {
  const [instructions, setInstructions] = useState("");
  const regenerationInstructions =
    instructions.trim().length > 0 ? instructions.trim() : undefined;

  return (
    <div className={`shrink-0 border-t border-zinc-200 bg-white px-4 py-3 ${className}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => onRegenerate("answer", regenerationInstructions)}
            disabled={isRegenerating}
            aria-busy={
              activeSuggestion?.mode === "answer" &&
              activeSuggestion.status === "loading"
            }
            className="flex h-8 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:bg-zinc-100 disabled:text-zinc-400"
          >
            {activeSuggestion?.mode === "answer" &&
            activeSuggestion.status === "loading" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Regenerate answer
          </button>
        </div>
        <div className="min-w-[240px] flex-1 space-y-1">
          <label
            className="block text-xs font-semibold text-zinc-600"
            htmlFor="regeneration-instructions"
          >
            Regeneration instructions
          </label>
          <textarea
            id="regeneration-instructions"
            value={instructions}
            onChange={(event) => setInstructions(event.target.value)}
            placeholder="Optional, e.g. add more explanation to the answer..."
            disabled={isRegenerating}
            className="block h-16 w-full resize-none rounded-md border border-zinc-300 bg-white p-2 text-sm text-zinc-900 outline-none transition-all placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-zinc-100 disabled:text-zinc-500"
          />
        </div>
        {activeSuggestion?.status === "loading" ? (
          <div className="flex items-center gap-2 text-xs font-medium text-zinc-500">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
            <span>Generating suggestion</span>
          </div>
        ) : null}
      </div>

      {activeSuggestion !== null ? (
        <div
          className={`mt-3 rounded-md border px-3 py-2 ${
            activeSuggestion.status === "error"
              ? "border-rose-200 bg-rose-50"
              : "border-zinc-200 bg-zinc-50"
          }`}
        >
          {activeSuggestion.status === "loading" ? (
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-600">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-600" />
              <span>Regenerating answer...</span>
            </div>
          ) : activeSuggestion.status === "error" ? (
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex min-w-0 items-start gap-2 text-sm text-rose-700">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
                <span className="whitespace-pre-wrap break-words">
                  {activeSuggestion.error}
                </span>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    onRegenerate(activeSuggestion.mode, regenerationInstructions)
                  }
                  className="flex h-8 items-center gap-2 rounded-md border border-rose-200 bg-white px-3 text-sm font-medium text-rose-700 transition-colors hover:bg-rose-50"
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry
                </button>
                <button
                  type="button"
                  onClick={onDiscard}
                  className="rounded-md border border-transparent p-1.5 text-rose-600 transition-colors hover:border-rose-200 hover:bg-white"
                  aria-label="Dismiss suggestion error"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid gap-2">
                <div className="min-w-0">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-zinc-500">
                    Suggested answer
                  </div>
                  <div className="max-h-28 overflow-auto whitespace-pre-wrap break-words rounded-md border border-zinc-200 bg-white p-2 text-sm leading-6 text-zinc-800">
                    {activeSuggestion.answer}
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap justify-end gap-2">
                <button
                  type="button"
                  onClick={onDiscard}
                  className="flex h-8 items-center gap-2 rounded-md border border-zinc-300 bg-white px-3 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50"
                >
                  <X className="h-4 w-4" />
                  Discard suggestion
                </button>
                <button
                  type="button"
                  onClick={onAccept}
                  className="flex h-8 items-center gap-2 rounded-md bg-zinc-800 px-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Accept suggestion
                </button>
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
