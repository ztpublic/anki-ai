import React, { useEffect, useRef, useState } from "react";
import {
  AssistantRuntimeProvider,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useExternalStoreRuntime,
  type MessageState,
  type ThreadMessageLike,
} from "@assistant-ui/react";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Info,
  Library,
  Loader2,
  MessageSquareText,
  Settings,
  Sparkles,
  Square,
  Trash2,
  UploadCloud,
  Wrench,
  X,
} from "lucide-react";
import { motion } from "motion/react";

import { BridgeTransportError } from "./bridge";

type Flashcard = {
  id: string;
  cardType: CardTypeId;
  front: string;
  back: string;
  explanation?: string;
};

type CardTypeId = "basic" | "answer_with_explanation";

type EditableCardField = "front" | "back" | "explanation";

type CardTypeDefinition = {
  id: CardTypeId;
  label: string;
  generationLabel: string;
  fields: {
    key: EditableCardField;
    label: string;
    placeholder: string;
    tone: "front" | "back";
  }[];
  toAnkiFields: (card: Flashcard) => Record<string, string>;
};

type Deck = {
  id: string;
  name: string;
  cardCount: number | null;
};

type DeckListResponse = {
  decks: Deck[];
};

type GenerationMaterialPayload = {
  name: string;
  contentBase64: string;
};

type GenerateCardsResponse = {
  cards: Flashcard[];
  run: {
    workspacePath: string;
    sessionId?: string;
    stopReason?: string;
  };
};

type StartGenerateCardsResponse = {
  jobId: string;
};

type GenerationJobError = {
  code: string;
  message: string;
  details?: unknown;
};

type GenerationJobEvent = {
  jobId: string;
  status: "started" | "log" | "succeeded" | "failed" | "cancelled";
  level?: "debug" | "info" | "warning" | "error";
  source?: "app" | "claude" | "llm";
  role?: string;
  message?: string;
  part?: LlmTracePartPayload;
  result?: GenerateCardsResponse;
  error?: GenerationJobError;
};

type AgentTraceLevel = "debug" | "info" | "warning" | "error";

type LlmTracePartPayload =
  | {
      type: "text" | "reasoning";
      text: string;
    }
  | {
      type: "tool-call";
      toolCallId?: string;
      toolName: string;
      argsText: string;
      serverSide?: boolean;
    }
  | {
      type: "data";
      name: string;
      data: unknown;
    };

type AgentTraceMessage = {
  id: string;
  role: "assistant" | "user";
  kind: "model_message" | "tool_call" | "agent_event" | "reasoning";
  label: string;
  level: AgentTraceLevel;
  source: "llm";
  part: LlmTracePartPayload;
  status: "streaming" | "done" | "error";
  createdAt: number;
};

type AgentMessagePart = {
  type: string;
  text?: string;
  name?: string;
  data?: unknown;
  toolName?: string;
  toolCallId?: string;
  args?: unknown;
  argsText?: string;
  result?: unknown;
  image?: string;
  filename?: string;
  dataRendererUI?: React.ReactNode;
  toolUI?: React.ReactNode;
  status?: {
    type: string;
    reason?: string;
  };
};

type InsertCardPayload = {
  fields: Record<string, string>;
  tags?: string[];
};

type InsertedCard = {
  id: string;
  noteId: string;
  deckId: string;
  question: string;
  answer: string;
  fields: Record<string, string>;
  tags: string[];
  state: Record<string, unknown>;
};

type NoteType = {
  id: string;
  name: string;
  fieldNames: string[];
};

type AddCardsResponse = {
  deck: Deck;
  noteType: NoteType;
  cards: InsertedCard[];
};

type SavedFlashcard = Flashcard & {
  deckId: string;
  deckName: string;
};

const DECK_LOAD_RETRY_DELAY_MS = 250;
const DECK_LOAD_MAX_ATTEMPTS = 20;
const SUPPORTED_ATTACHMENT_EXTENSIONS = [
  ".atom",
  ".csv",
  ".docx",
  ".epub",
  ".htm",
  ".html",
  ".ipynb",
  ".jpeg",
  ".jpg",
  ".json",
  ".jsonl",
  ".m4a",
  ".markdown",
  ".md",
  ".mp3",
  ".mp4",
  ".msg",
  ".pdf",
  ".png",
  ".pptx",
  ".rss",
  ".text",
  ".txt",
  ".wav",
  ".xls",
  ".xlsx",
  ".xml",
  ".zip",
] as const;
const SUPPORTED_ATTACHMENT_EXTENSION_SET = new Set<string>(
  SUPPORTED_ATTACHMENT_EXTENSIONS,
);
const SUPPORTED_ATTACHMENT_ACCEPT = SUPPORTED_ATTACHMENT_EXTENSIONS.join(",");
const SUPPORTED_ATTACHMENT_SUMMARY =
  "PDF, Office, text, web, data, image, audio/video, ZIP";

const DEFAULT_CARD_TYPE_ID: CardTypeId = "basic";

function combineAnswerAndExplanation(card: Flashcard): string {
  const answer = card.back.trim();
  const explanation = card.explanation?.trim() ?? "";

  if (!explanation) {
    return answer;
  }

  if (!answer) {
    return explanation;
  }

  return `${answer}\n\nExplanation:\n${explanation}`;
}

const CARD_TYPES: Record<CardTypeId, CardTypeDefinition> = {
  basic: {
    id: "basic",
    label: "Question and Answer",
    generationLabel: "Q&A",
    fields: [
      {
        key: "front",
        label: "Front (Question)",
        placeholder: "Type the question here...",
        tone: "front",
      },
      {
        key: "back",
        label: "Back (Answer)",
        placeholder: "Type the answer here...",
        tone: "back",
      },
    ],
    toAnkiFields: (card) => ({
      Front: card.front,
      Back: card.back,
    }),
  },
  answer_with_explanation: {
    id: "answer_with_explanation",
    label: "Answer with Explanation",
    generationLabel: "Answer + explanation",
    fields: [
      {
        key: "front",
        label: "Front (Question)",
        placeholder: "Type the question here...",
        tone: "front",
      },
      {
        key: "back",
        label: "Back (Answer)",
        placeholder: "Type the answer here...",
        tone: "back",
      },
      {
        key: "explanation",
        label: "Explanation",
        placeholder: "Add the explanation here...",
        tone: "back",
      },
    ],
    toAnkiFields: (card) => ({
      Front: card.front,
      Back: combineAnswerAndExplanation(card),
    }),
  },
};

const CARD_TYPE_OPTIONS = Object.values(CARD_TYPES);

function normalizeCardType(cardType: unknown): CardTypeId {
  return typeof cardType === "string" && cardType in CARD_TYPES
    ? (cardType as CardTypeId)
    : DEFAULT_CARD_TYPE_ID;
}

function cardTypeDefinition(card: Flashcard): CardTypeDefinition {
  return CARD_TYPES[card.cardType] ?? CARD_TYPES[DEFAULT_CARD_TYPE_ID];
}

function createCardId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function deckOptionLabel(deck: Deck): string {
  if (deck.cardCount === null) {
    return deck.name;
  }

  return `${deck.name} (${deck.cardCount})`;
}

function deckErrorMessage(error: unknown): string {
  if (error instanceof BridgeTransportError) {
    if (error.code === "bridge_unavailable") {
      return "Open in Anki to load decks.";
    }

    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Decks could not be loaded.";
}

function saveErrorMessage(error: unknown): string {
  if (error instanceof BridgeTransportError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Cards could not be saved.";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function generationErrorMessage(error: unknown): string {
  if (error instanceof BridgeTransportError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Cards could not be generated.";
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error(`Could not read ${file.name}.`));
        return;
      }

      const commaIndex = result.indexOf(",");
      resolve(commaIndex === -1 ? result : result.slice(commaIndex + 1));
    };

    reader.onerror = () => {
      reject(reader.error ?? new Error(`Could not read ${file.name}.`));
    };

    reader.readAsDataURL(file);
  });
}

function isGenerationJobEvent(value: unknown): value is GenerationJobEvent {
  if (!isRecord(value)) {
    return false;
  }

  return (
    typeof value.jobId === "string" &&
    typeof value.status === "string" &&
    ["started", "log", "succeeded", "failed", "cancelled"].includes(
      value.status,
    )
  );
}

function generationErrorFromJob(error: GenerationJobError | undefined): string {
  if (error?.message) {
    return error.message;
  }

  return "Cards could not be generated.";
}

function fileExtension(fileName: string): string {
  const trimmedName = fileName.trim().toLowerCase();
  const lastDotIndex = trimmedName.lastIndexOf(".");
  if (lastDotIndex <= 0) {
    return "";
  }

  return trimmedName.slice(lastDotIndex);
}

function isSupportedAttachmentFile(file: File): boolean {
  return SUPPORTED_ATTACHMENT_EXTENSION_SET.has(fileExtension(file.name));
}

function traceMessageMetadata(message: AgentTraceMessage) {
  return {
    kind: message.kind,
    label: message.label,
    level: message.level,
    source: message.source,
    role: message.role,
  };
}

function traceMessageStatus(
  message: AgentTraceMessage,
): ThreadMessageLike["status"] {
  if (message.level === "error") {
    return { type: "incomplete", reason: "error" };
  }

  if (
    (message.kind === "model_message" || message.kind === "reasoning") &&
    message.status === "streaming"
  ) {
    return { type: "running" };
  }

  return { type: "complete", reason: "stop" };
}

function traceContent(message: AgentTraceMessage): ThreadMessageLike["content"] {
  const part = message.part;

  if (part.type === "tool-call") {
    if (message.role === "assistant") {
      return [
        {
          type: "tool-call",
          toolCallId: part.toolCallId ?? message.id,
          toolName: part.toolName,
          argsText: part.argsText,
        },
      ];
    }

    return [
      {
        type: "data",
        name: "tool-call",
        data: part,
      },
    ];
  }

  if (part.type === "data") {
    return [
      {
        type: "data",
        name: part.name,
        data: part.data,
      },
    ];
  }

  if (part.type === "reasoning" && message.role === "assistant") {
    return [
      {
        type: "reasoning",
        text: part.text,
      },
    ];
  }

  return [
    {
      type: "text",
      text: part.text,
    },
  ];
}

function convertTraceMessage(message: AgentTraceMessage): ThreadMessageLike {
  const base = {
    id: message.id,
    role: message.role,
    createdAt: new Date(message.createdAt),
    content: traceContent(message),
    metadata: {
      custom: traceMessageMetadata(message),
    },
  };

  if (message.role === "assistant") {
    return {
      ...base,
      role: "assistant",
      status: traceMessageStatus(message),
    };
  }

  return {
    ...base,
    role: "user",
  };
}

function readOnlyTranscriptError(): never {
  throw new Error("The generation transcript is read-only.");
}

function AgentTranscriptRuntimeProvider({
  messages,
  isRunning,
  children,
}: {
  messages: AgentTraceMessage[];
  isRunning: boolean;
  children: React.ReactNode;
}) {
  const runtime = useExternalStoreRuntime<AgentTraceMessage>({
    messages,
    isRunning,
    convertMessage: convertTraceMessage,
    onNew: async () => {
      readOnlyTranscriptError();
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}

function stripRolePrefix(message: string, role: string | undefined): string {
  if (role && message.startsWith(`${role}:`)) {
    return message.slice(role.length + 1).trim();
  }

  return message.trim();
}

function traceRoleFromEvent(role: string | undefined): AgentTraceMessage["role"] {
  return role === "Claude Code -> LLM" ? "user" : "assistant";
}

function traceLabelFromEvent(role: string | undefined): string {
  if (role === "Claude Code -> LLM") {
    return "Agent -> LLM";
  }

  if (role === "LLM -> Claude Code") {
    return "LLM -> Agent";
  }

  return role ?? "LLM message";
}

function traceKindFromPart(part: LlmTracePartPayload): AgentTraceMessage["kind"] {
  if (part.type === "tool-call") {
    return "tool_call";
  }

  if (part.type === "reasoning") {
    return "reasoning";
  }

  if (part.type === "data") {
    return "agent_event";
  }

  return "model_message";
}

function traceFromGenerationLogEvent(
  event: GenerationJobEvent,
): AgentTraceMessage | null {
  if (event.source !== "llm") {
    return null;
  }

  const message = event.message?.trim();
  if (!message) {
    return null;
  }

  const level = event.level ?? "info";
  const createdAt = Date.now();
  const role = event.role;
  const traceRole = traceRoleFromEvent(role);
  const label = traceLabelFromEvent(role);

  if (event.part !== undefined) {
    return {
      id: createCardId(),
      role: traceRole,
      kind: traceKindFromPart(event.part),
      label,
      level,
      source: "llm",
      part: event.part,
      status: level === "error" ? "error" : "done",
      createdAt,
    };
  }

  const toolRequestMatch = message.match(
    /^(.*?) tool request: ([^\s]+)(?:\s+([\s\S]*))?$/,
  );
  if (toolRequestMatch) {
    const argsText = toolRequestMatch[3]?.trim() ?? "";
    return {
      id: createCardId(),
      role: traceRole,
      kind: "tool_call",
      label,
      level,
      source: "llm",
      part: {
        type: "tool-call",
        toolCallId: createCardId(),
        toolName: toolRequestMatch[2] ?? "Tool",
        argsText,
      },
      status: level === "error" ? "error" : "done",
      createdAt,
    };
  }

  const toolResultMatch = message.match(
    /^(.*?) tool result( error)?(?:\s+([^:]+))?:?\s*([\s\S]*)$/,
  );
  if (toolResultMatch) {
    return {
      id: createCardId(),
      role: traceRole,
      kind: "agent_event",
      label: toolResultMatch[2] ? "Tool result failed" : "Tool result",
      level: toolResultMatch[2] ? "error" : level,
      source: "llm",
      part: {
        type: "data",
        name: "tool-result",
        data: {
          content: toolResultMatch[4]?.trim() || undefined,
          isError: Boolean(toolResultMatch[2]),
        },
      },
      status: toolResultMatch[2] ? "error" : "done",
      createdAt,
    };
  }

  return {
    id: createCardId(),
    role: traceRole,
    kind: "model_message",
    label,
    level,
    source: "llm",
    part: {
      type: "text",
      text: stripRolePrefix(message, role),
    },
    status: level === "error" ? "error" : "done",
    createdAt,
  };
}

function traceLevelClass(level: unknown): string {
  if (level === "error") {
    return "border-rose-200 bg-rose-50 text-rose-900";
  }

  if (level === "warning") {
    return "border-amber-200 bg-amber-50 text-amber-900";
  }

  return "border-zinc-200 bg-white text-zinc-800";
}

function traceAccentClass(level: unknown): string {
  if (level === "error") {
    return "bg-rose-500";
  }

  if (level === "warning") {
    return "bg-amber-500";
  }

  return "bg-indigo-500";
}

function traceIcon(kind: unknown) {
  if (kind === "tool_call") {
    return <Wrench className="h-3.5 w-3.5" />;
  }

  if (kind === "reasoning") {
    return <Sparkles className="h-3.5 w-3.5" />;
  }

  if (kind === "agent_event") {
    return <Info className="h-3.5 w-3.5" />;
  }

  return <Bot className="h-3.5 w-3.5" />;
}

function traceLabel(message: MessageState): string {
  const custom = message.metadata.custom;
  const label = custom.label;
  if (typeof label === "string" && label.trim()) {
    return label;
  }

  return "LLM message";
}

function formatToolValue(value: unknown): string {
  if (value === undefined || value === null) {
    return "";
  }

  if (typeof value === "string") {
    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function AgentTranscript() {
  return (
    <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
      <ThreadPrimitive.Viewport
        autoScroll
        turnAnchor="bottom"
        className="min-h-0 flex-1 overflow-y-auto bg-white p-4"
      >
        <ThreadPrimitive.Empty>
          <div className="flex h-full items-center justify-center text-sm text-zinc-500">
            Waiting for LLM messages...
          </div>
        </ThreadPrimitive.Empty>
        <ThreadPrimitive.Messages>
          {({ message }: { message: MessageState }) => (
            <AgentMessage message={message} />
          )}
        </ThreadPrimitive.Messages>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function AgentMessage({ message }: { message: MessageState }) {
  const custom = message.metadata.custom;
  const kind = custom.kind;
  const level = custom.level;

  return (
    <MessagePrimitive.Root className="mb-3 last:mb-0">
      <div
        className={`relative overflow-hidden rounded-md border p-3 text-sm shadow-sm ${traceLevelClass(
          level,
        )}`}
      >
        <div
          className={`absolute left-0 top-0 h-full w-1 ${traceAccentClass(
            level,
          )}`}
        />
        <div className="mb-2 flex min-w-0 items-center gap-2 pl-1 text-xs font-semibold text-zinc-600">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-zinc-200 bg-white text-zinc-500">
            {traceIcon(kind)}
          </span>
          <span className="min-w-0 truncate">{traceLabel(message)}</span>
        </div>
        <div className="pl-1">
          <MessagePrimitive.Parts>
            {({ part }: { part: AgentMessagePart }) => {
              if (part.type === "text") {
                return <AgentTextPart />;
              }

              if (part.type === "reasoning") {
                return <AgentReasoningPart />;
              }

              if (part.type === "tool-call") {
                return <AgentToolCallPartView part={part} />;
              }

              if (part.type === "data") {
                return <AgentDataPartView part={part} />;
              }

              if (part.type === "image" && part.image) {
                return (
                  <img
                    src={part.image}
                    alt={part.filename ?? "LLM image"}
                    className="max-h-72 max-w-full rounded border border-zinc-200"
                  />
                );
              }

              if (part.type === "file") {
                return <AgentDataPartView part={part} />;
              }

              return null;
            }}
          </MessagePrimitive.Parts>
        </div>
      </div>
    </MessagePrimitive.Root>
  );
}

function AgentReasoningPart() {
  return (
    <details
      open
      className="rounded-md border border-indigo-100 bg-indigo-50/50 p-2 text-zinc-800"
    >
      <summary className="cursor-pointer text-sm font-semibold text-indigo-800">
        Thinking
      </summary>
      <div className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 [overflow-wrap:anywhere]">
        <MessagePartPrimitive.Text />
        <MessagePartPrimitive.InProgress>
          <span className="ml-1 animate-pulse text-indigo-600">▊</span>
        </MessagePartPrimitive.InProgress>
      </div>
    </details>
  );
}

function AgentTextPart() {
  return (
    <div className="whitespace-pre-wrap break-words leading-6 text-inherit [overflow-wrap:anywhere]">
      <MessagePartPrimitive.Text />
      <MessagePartPrimitive.InProgress>
        <span className="ml-1 animate-pulse text-indigo-600">▊</span>
      </MessagePartPrimitive.InProgress>
    </div>
  );
}

function AgentToolCallPartView({ part }: { part: AgentMessagePart }) {
  const args = formatToolValue(part.args) || part.argsText || "";
  const result = formatToolValue(part.result);

  return (
    <details
      open
      className="rounded-md border border-zinc-200 bg-zinc-50 p-2 text-zinc-800"
    >
      <summary className="cursor-pointer text-sm font-semibold">
        {part.toolName ?? "Tool call"}
      </summary>
      {args ? (
        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded border border-zinc-200 bg-white p-2 text-xs leading-5 text-zinc-700">
          {args}
        </pre>
      ) : null}
      {result ? (
        <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded border border-zinc-200 bg-white p-2 text-xs leading-5 text-zinc-700">
          {result}
        </pre>
      ) : null}
    </details>
  );
}

function AgentDataPartView({ part }: { part: AgentMessagePart }) {
  const rendered = part.dataRendererUI;
  if (rendered) {
    return rendered;
  }

  const title =
    part.name === "tool-result"
      ? "Tool result"
      : part.name === "server-tool-result"
        ? "Server tool result"
        : part.name ?? part.filename ?? "Data";
  const value =
    part.data !== undefined
      ? part.data
      : {
          filename: part.filename,
          text: part.text,
        };

  return (
    <details
      open
      className="rounded-md border border-zinc-200 bg-zinc-50 p-2 text-zinc-800"
    >
      <summary className="cursor-pointer text-sm font-semibold">{title}</summary>
      <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap rounded border border-zinc-200 bg-white p-2 text-xs leading-5 text-zinc-700">
        {formatToolValue(value)}
      </pre>
    </details>
  );
}

export function App() {
  const [inputText, setInputText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [cardCount, setCardCount] = useState(5);
  const [selectedCardTypeId, setSelectedCardTypeId] =
    useState<CardTypeId>(DEFAULT_CARD_TYPE_ID);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedCards, setGeneratedCards] = useState<Flashcard[]>([]);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [savedLibrary, setSavedLibrary] = useState<SavedFlashcard[]>([]);
  const [decks, setDecks] = useState<Deck[]>([]);
  const [selectedDeckId, setSelectedDeckId] = useState("");
  const [isLoadingDecks, setIsLoadingDecks] = useState(true);
  const [deckLoadError, setDeckLoadError] = useState<string | null>(null);
  const [isSavingCards, setIsSavingCards] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(
    null,
  );
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [agentTraceMessages, setAgentTraceMessages] = useState<
    AgentTraceMessage[]
  >([]);
  const [showAgentMessages, setShowAgentMessages] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeGenerationJobIdRef = useRef<string | null>(null);
  const acceptsGenerationEventsRef = useRef(false);
  const stopGenerationRequestedRef = useRef(false);
  const generationRequestIdRef = useRef(0);
  const currentCard = generatedCards[currentCardIndex];
  const currentCardType = currentCard ? cardTypeDefinition(currentCard) : null;
  const canGenerate = inputText.trim().length > 0 || files.length > 0;
  const selectedDeck =
    decks.find((deck) => deck.id === selectedDeckId) ?? null;
  const canSaveCards =
    selectedDeck !== null && generatedCards.length > 0 && !isSavingCards;

  useEffect(() => {
    let cancelled = false;
    let retryTimeoutId: number | undefined;
    let attempts = 0;

    const loadDecks = async () => {
      setIsLoadingDecks(true);
      setDeckLoadError(null);

      try {
        const result = await window.AnkiAI.call<DeckListResponse>(
          "anki.decks.list",
          { includeCardCounts: true },
          { timeoutMs: 5000 },
        );
        if (cancelled) {
          return;
        }

        const nextDecks = result.decks;
        setDecks(nextDecks);
        setSelectedDeckId((previousDeckId) => {
          if (nextDecks.some((deck) => deck.id === previousDeckId)) {
            return previousDeckId;
          }

          return nextDecks[0]?.id ?? "";
        });

        if (nextDecks.length === 0) {
          setDeckLoadError("No decks found in the active collection.");
        }
        setIsLoadingDecks(false);
      } catch (error) {
        if (
          error instanceof BridgeTransportError &&
          error.code === "bridge_unavailable" &&
          attempts < DECK_LOAD_MAX_ATTEMPTS
        ) {
          attempts += 1;
          retryTimeoutId = window.setTimeout(() => {
            void loadDecks();
          }, DECK_LOAD_RETRY_DELAY_MS);
          return;
        }

        if (cancelled) {
          return;
        }

        setDecks([]);
        setSelectedDeckId("");
        setDeckLoadError(deckErrorMessage(error));
        setIsLoadingDecks(false);
      }
    };

    void loadDecks();

    return () => {
      cancelled = true;
      if (retryTimeoutId !== undefined) {
        window.clearTimeout(retryTimeoutId);
      }
    };
  }, []);

  useEffect(() => {
    return window.AnkiAI.on<GenerationJobEvent>(
      "anki.generation.job",
      (event) => {
        if (!isGenerationJobEvent(event)) {
          return;
        }

        const activeJobId = activeGenerationJobIdRef.current;
        if (activeJobId !== null && event.jobId !== activeJobId) {
          return;
        }
        if (activeJobId === null && !acceptsGenerationEventsRef.current) {
          return;
        }

        activeGenerationJobIdRef.current = event.jobId;

        if (event.status === "started") {
          return;
        }

        if (event.status === "log") {
          const traceMessage = traceFromGenerationLogEvent(event);
          if (traceMessage !== null) {
            setAgentTraceMessages((previousMessages) => [
              ...previousMessages,
              traceMessage,
            ]);
          }
          return;
        }

        if (event.status === "succeeded") {
          if (!event.result) {
            const message = "Generation finished without a result payload.";
            setGenerationError(message);
            setIsGenerating(false);
            setShowAgentMessages(true);
            acceptsGenerationEventsRef.current = false;
            activeGenerationJobIdRef.current = null;
            return;
          }

          setGeneratedCards(
            event.result.cards.map((card) => ({
              id: card.id || createCardId(),
              cardType: normalizeCardType(card.cardType),
              front: card.front,
              back: card.back,
              explanation: card.explanation,
            })),
          );
          setCurrentCardIndex(0);
          setGenerationError(null);
          setIsGenerating(false);
          setShowAgentMessages(false);
          acceptsGenerationEventsRef.current = false;
          activeGenerationJobIdRef.current = null;
          return;
        }

        if (event.status === "cancelled") {
          setGenerationError(null);
          setIsGenerating(false);
          setShowAgentMessages(true);
          acceptsGenerationEventsRef.current = false;
          activeGenerationJobIdRef.current = null;
          stopGenerationRequestedRef.current = false;
          return;
        }

        const message = generationErrorFromJob(event.error);
        setGenerationError(message);
        setIsGenerating(false);
        setShowAgentMessages(true);
        acceptsGenerationEventsRef.current = false;
        activeGenerationJobIdRef.current = null;
        stopGenerationRequestedRef.current = false;
      },
    );
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    const supportedFiles = selectedFiles.filter(isSupportedAttachmentFile);
    const unsupportedFiles = selectedFiles.filter(
      (file) => !isSupportedAttachmentFile(file),
    );

    if (supportedFiles.length > 0) {
      setFiles((previousFiles) => [...previousFiles, ...supportedFiles]);
      setGenerationError(null);
    }

    if (unsupportedFiles.length > 0) {
      const names = unsupportedFiles.map((file) => file.name).join(", ");
      setGenerationError(
        `Unsupported file type: ${names}\nSupported files: ${SUPPORTED_ATTACHMENT_SUMMARY}.`,
      );
    }

    if (selectedFiles.length > 0) {
      event.target.value = "";
    }
  };

  const removeFile = (indexToRemove: number) => {
    setFiles((previousFiles) =>
      previousFiles.filter((_, index) => index !== indexToRemove),
    );
  };

  const handleGenerate = async () => {
    if (isGenerating) {
      stopGenerationRequestedRef.current = true;
      generationRequestIdRef.current += 1;
      const jobId = activeGenerationJobIdRef.current;
      setIsGenerating(false);

      if (jobId === null) {
        acceptsGenerationEventsRef.current = false;
        return;
      }

      acceptsGenerationEventsRef.current = false;
      activeGenerationJobIdRef.current = null;

      try {
        await window.AnkiAI.call(
          "anki.generation.stopGenerateCards",
          { jobId },
          { timeoutMs: 5000 },
        );
      } catch (error) {
        setGenerationError(generationErrorMessage(error));
        setShowAgentMessages(true);
      }
      return;
    }

    if (!canGenerate) {
      return;
    }

    stopGenerationRequestedRef.current = false;
    const requestId = generationRequestIdRef.current + 1;
    generationRequestIdRef.current = requestId;
    setGenerationError(null);
    setSaveError(null);
    setSaveSuccessMessage(null);
    setIsGenerating(true);
    setShowAgentMessages(true);
    setAgentTraceMessages([]);
    setGeneratedCards([]);
    setCurrentCardIndex(0);
    activeGenerationJobIdRef.current = null;
    acceptsGenerationEventsRef.current = true;

    await new Promise((resolve) => {
      window.setTimeout(resolve, 0);
    });

    try {
      const materials = await Promise.all<GenerationMaterialPayload>(
        files.map(async (file) => ({
          name: file.name,
          contentBase64: await fileToBase64(file),
        })),
      );

      const result = await window.AnkiAI.call<StartGenerateCardsResponse>(
        "anki.generation.startGenerateCards",
        {
          sourceText: inputText.trim().length > 0 ? inputText : undefined,
          cardCount,
          cardType: selectedCardTypeId,
          materials,
        },
        { timeoutMs: 10000 },
      );

      if (
        requestId !== generationRequestIdRef.current ||
        stopGenerationRequestedRef.current
      ) {
        acceptsGenerationEventsRef.current = false;
        activeGenerationJobIdRef.current = null;
        await window.AnkiAI.call(
          "anki.generation.stopGenerateCards",
          { jobId: result.jobId },
          { timeoutMs: 5000 },
        );
        stopGenerationRequestedRef.current = false;
        return;
      }

      activeGenerationJobIdRef.current = result.jobId;
    } catch (error) {
      if (requestId !== generationRequestIdRef.current) {
        return;
      }

      acceptsGenerationEventsRef.current = false;
      activeGenerationJobIdRef.current = null;
      stopGenerationRequestedRef.current = false;
      setGenerationError(generationErrorMessage(error));
      setIsGenerating(false);
      setShowAgentMessages(true);
    }
  };

  const handleDiscard = () => {
    setGeneratedCards((previousCards) =>
      previousCards.filter((_, index) => index !== currentCardIndex),
    );
    setCurrentCardIndex((previousIndex) =>
      Math.max(0, Math.min(previousIndex, generatedCards.length - 2)),
    );
  };

  const handleFinish = async () => {
    if (selectedDeck === null || generatedCards.length === 0 || isSavingCards) {
      return;
    }

    setIsSavingCards(true);
    setSaveError(null);
    setSaveSuccessMessage(null);

    try {
      const result = await window.AnkiAI.call<AddCardsResponse>(
        "anki.cards.addToDeck",
        {
          deckId: selectedDeck.id,
          noteTypeName: "Basic",
          cards: generatedCards.map<InsertCardPayload>((card) => ({
            fields: cardTypeDefinition(card).toAnkiFields(card),
          })),
        },
        { timeoutMs: 15000 },
      );

      const savedCards = result.cards.map((card) => ({
        id: card.id,
        cardType: DEFAULT_CARD_TYPE_ID,
        front: card.fields.Front ?? card.question,
        back: card.fields.Back ?? card.answer,
        deckId: result.deck.id,
        deckName: result.deck.name,
      }));

      setSavedLibrary((previousCards) => [...previousCards, ...savedCards]);
      setDecks((previousDecks) =>
        previousDecks.map((deck) => {
          if (deck.id !== result.deck.id || deck.cardCount === null) {
            return deck;
          }

          return {
            ...deck,
            cardCount: deck.cardCount + result.cards.length,
          };
        }),
      );
      setGeneratedCards([]);
      setCurrentCardIndex(0);
      setSaveSuccessMessage(
        `Saved ${result.cards.length} cards to ${result.deck.name}.`,
      );
    } catch (error) {
      setSaveError(saveErrorMessage(error));
    } finally {
      setIsSavingCards(false);
    }
  };

  const handleCardUpdate = (field: EditableCardField, value: string) => {
    setGeneratedCards((previousCards) =>
      previousCards.map((card, index) =>
        index === currentCardIndex ? { ...card, [field]: value } : card,
      ),
    );
  };

  return (
    <div className="flex h-full overflow-hidden bg-zinc-200 p-4 font-sans text-zinc-900 selection:bg-indigo-100 selection:text-indigo-900">
      <main className="mx-auto flex h-full max-h-[820px] min-h-0 w-full max-w-6xl flex-col overflow-hidden rounded-lg border border-zinc-300 bg-zinc-50 shadow-[0_8px_30px_rgba(24,24,27,0.14)] lg:flex-row">
        <section className="flex min-h-0 w-full flex-col border-b border-zinc-300 bg-zinc-100 lg:w-[330px] lg:border-b-0 lg:border-r">
          <div className="flex h-11 shrink-0 items-center justify-between border-b border-zinc-300 bg-zinc-100 px-4">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-800">
              <Settings className="h-4 w-4 text-zinc-500" />
              Generator Settings
            </h2>
            <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-500">
              <Library className="h-3.5 w-3.5" />
              <span>{savedLibrary.length}</span>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
            <div className="space-y-1.5">
              <label
                className="block text-xs font-semibold text-zinc-600"
                htmlFor="target-deck"
              >
                Target Deck
              </label>
              <select
                id="target-deck"
                value={selectedDeckId}
                onChange={(event) => setSelectedDeckId(event.target.value)}
                disabled={isLoadingDecks || decks.length === 0}
                className="block h-8 w-full rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 outline-none transition-all focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 disabled:bg-zinc-100 disabled:text-zinc-500"
              >
                {isLoadingDecks ? (
                  <option value="">Loading decks...</option>
                ) : null}
                {!isLoadingDecks && decks.length === 0 ? (
                  <option value="">No decks available</option>
                ) : null}
                {decks.map((deck) => (
                  <option key={deck.id} value={deck.id}>
                    {deckOptionLabel(deck)}
                  </option>
                ))}
              </select>
              {deckLoadError !== null ? (
                <div className="flex items-center gap-1.5 text-xs font-medium text-rose-600">
                  <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                  <span className="truncate">{deckLoadError}</span>
                </div>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <label
                className="block text-xs font-semibold text-zinc-600"
                htmlFor="card-type"
              >
                Card Type
              </label>
              <select
                id="card-type"
                value={selectedCardTypeId}
                onChange={(event) =>
                  setSelectedCardTypeId(event.target.value as CardTypeId)
                }
                className="block h-8 w-full rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 outline-none transition-all focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              >
                {CARD_TYPE_OPTIONS.map((cardType) => (
                  <option key={cardType.id} value={cardType.id}>
                    {cardType.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label
                className="block text-xs font-semibold text-zinc-600"
                htmlFor="source-text"
              >
                Source Text
              </label>
              <textarea
                id="source-text"
                value={inputText}
                onChange={(event) => setInputText(event.target.value)}
                placeholder="Paste the text you want to convert into flashcards..."
                className="block h-32 w-full resize-none rounded-md border border-zinc-300 bg-white p-2.5 text-sm text-zinc-900 outline-none transition-all placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-zinc-600">
                Additional Files
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="group flex w-full flex-col items-center justify-center rounded-md border border-dashed border-zinc-300 bg-white p-3 text-center transition-all hover:border-indigo-300 hover:bg-indigo-50/40"
              >
                <UploadCloud className="mb-2 h-5 w-5 text-zinc-400 transition-colors group-hover:text-indigo-500" />
                <span className="text-sm font-medium text-zinc-700">
                  Click to upload documents
                </span>
                <span className="mt-0.5 text-xs text-zinc-500">
                  {SUPPORTED_ATTACHMENT_SUMMARY}
                </span>
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="hidden"
                multiple
                accept={SUPPORTED_ATTACHMENT_ACCEPT}
              />

              {files.length > 0 ? (
                <div className="mt-3 flex flex-col gap-2">
                  {files.map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="flex items-center justify-between rounded-md border border-zinc-300 bg-white p-1.5 pl-2.5 text-sm"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 flex-shrink-0 text-zinc-400" />
                        <span className="truncate text-zinc-700">
                          {file.name}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="rounded p-1 text-zinc-500 transition-colors hover:bg-zinc-200"
                        aria-label={`Remove ${file.name}`}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <label
                className="flex justify-between text-xs font-semibold text-zinc-600"
                htmlFor="card-count"
              >
                <span>Number of Cards</span>
                <span className="text-indigo-600">{cardCount}</span>
              </label>
              <input
                id="card-count"
                type="range"
                min="1"
                max="200"
                value={cardCount}
                onChange={(event) => setCardCount(Number(event.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded bg-zinc-300 accent-indigo-600"
              />
            </div>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={!isGenerating && !canGenerate}
              aria-busy={isGenerating}
              className={`mt-auto flex h-9 w-full items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold text-white transition-colors disabled:bg-zinc-300 disabled:text-zinc-500 disabled:hover:bg-zinc-300 ${
                isGenerating
                  ? "bg-rose-600 hover:bg-rose-700"
                  : "bg-indigo-600 hover:bg-indigo-700"
              }`}
            >
              {isGenerating ? (
                <>
                  <Square className="h-4 w-4 fill-current" />
                  Stop generating
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Generate
                </>
              )}
            </button>
            {generationError !== null ? (
              <div className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                <span className="whitespace-pre-wrap break-words">
                  {generationError}
                </span>
              </div>
            ) : null}
          </div>
        </section>

        <section className="flex min-h-0 min-w-0 w-full flex-1 flex-col bg-zinc-50">
          {showAgentMessages ? (
            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-zinc-50">
              <div className="flex h-11 shrink-0 items-center justify-between border-b border-zinc-300 bg-zinc-100 px-4">
                <h2 className="flex min-w-0 items-center gap-2 text-sm font-semibold text-zinc-800">
                  <MessageSquareText className="h-4 w-4 shrink-0 text-zinc-500" />
                  LLM Agent Messages
                </h2>
                <div className="flex shrink-0 items-center gap-2 text-xs font-medium text-zinc-500">
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-600" />
                      <span>Generating</span>
                    </>
                  ) : generationError !== null ? (
                    <span className="text-rose-600">Failed</span>
                  ) : (
                    <span>Idle</span>
                  )}
                </div>
              </div>
              <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
                <AgentTranscriptRuntimeProvider
                  messages={agentTraceMessages}
                  isRunning={isGenerating}
                >
                  <AgentTranscript />
                </AgentTranscriptRuntimeProvider>
              </div>
            </div>
          ) : generatedCards.length > 0 && currentCard && currentCardType ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex h-11 shrink-0 items-center justify-between border-b border-zinc-300 bg-zinc-100 px-4">
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-zinc-800">
                    Review Cards
                  </h2>
                  <div className="truncate text-xs font-medium text-zinc-500">
                    {currentCardType.label}
                  </div>
                </div>
                <div className="flex min-w-0 items-center gap-2 text-xs font-medium text-zinc-500">
                  {selectedDeck !== null ? (
                    <span
                      className="max-w-[220px] truncate"
                      title={selectedDeck.name}
                    >
                      {selectedDeck.name}
                    </span>
                  ) : null}
                  <span className="shrink-0">
                    {currentCardIndex + 1} / {generatedCards.length}
                  </span>
                </div>
              </div>

              <motion.div
                key={currentCard.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.2 }}
                className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white"
              >
                {currentCardType.fields.map((field, fieldIndex) => (
                  <div
                    key={field.key}
                    className={
                      field.tone === "front"
                        ? "flex min-h-0 flex-1 flex-col border-b border-zinc-200 p-5"
                        : fieldIndex === currentCardType.fields.length - 1
                          ? "flex min-h-0 flex-1 flex-col bg-zinc-50 p-5"
                          : "flex min-h-0 flex-1 flex-col border-b border-zinc-200 bg-zinc-50 p-5"
                    }
                  >
                    <label
                      className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500"
                      htmlFor={`card-${field.key}`}
                    >
                      {field.label}
                    </label>
                    <textarea
                      id={`card-${field.key}`}
                      value={currentCard[field.key] ?? ""}
                      onChange={(event) =>
                        handleCardUpdate(field.key, event.target.value)
                      }
                      className={
                        field.tone === "front"
                          ? "min-h-0 w-full flex-1 resize-none rounded-md border border-transparent bg-transparent p-2 text-base text-zinc-800 outline-none placeholder:text-zinc-300 focus:border-indigo-200 focus:bg-indigo-50/20"
                          : "min-h-0 w-full flex-1 resize-none rounded-md border border-transparent bg-transparent p-2 text-base text-zinc-800 outline-none placeholder:text-zinc-300 focus:border-indigo-200 focus:bg-white"
                      }
                      placeholder={field.placeholder}
                    />
                  </div>
                ))}
              </motion.div>

              <div className="flex h-14 shrink-0 items-center justify-between border-t border-zinc-300 bg-zinc-100 px-4">
                <button
                  type="button"
                  onClick={handleDiscard}
                  className="flex h-8 items-center gap-2 rounded-md border border-transparent px-3 text-sm font-medium text-rose-600 transition-colors hover:border-rose-200 hover:bg-rose-50"
                >
                  <Trash2 className="h-4 w-4" />
                  Discard
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentCardIndex((previousIndex) =>
                        Math.max(0, previousIndex - 1),
                      )
                    }
                    disabled={currentCardIndex === 0}
                    className="rounded-md border border-zinc-300 bg-white p-1.5 text-zinc-600 transition-colors hover:bg-zinc-50 disabled:opacity-50"
                    aria-label="Previous card"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setCurrentCardIndex((previousIndex) =>
                        Math.min(generatedCards.length - 1, previousIndex + 1),
                      )
                    }
                    disabled={currentCardIndex === generatedCards.length - 1}
                    className="rounded-md border border-zinc-300 bg-white p-1.5 text-zinc-600 transition-colors hover:bg-zinc-50 disabled:opacity-50"
                    aria-label="Next card"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleFinish}
                  disabled={!canSaveCards}
                  className="flex h-8 items-center gap-2 rounded-md bg-zinc-800 px-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:bg-zinc-300 disabled:text-zinc-500 disabled:hover:bg-zinc-300"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  {isSavingCards ? "Saving..." : `Save ${generatedCards.length} Cards`}
                </button>
              </div>
              {saveError !== null ? (
                <div className="border-t border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700">
                  {saveError}
                </div>
              ) : null}
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center bg-zinc-50 p-8 text-center">
              <div className="mb-4 rounded-md border border-zinc-300 bg-white p-3 shadow-sm">
                <Library className="h-7 w-7 text-zinc-400" />
              </div>
              <h3 className="mb-2 text-base font-semibold text-zinc-800">
                Ready to generate
              </h3>
              <p className="max-w-sm text-sm text-zinc-500">
                Provide source text or upload documents and generate a new deck
                of Anki flashcards.
              </p>
              {!canGenerate ? (
                <div className="mt-5 flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-500">
                  <AlertCircle className="h-4 w-4" />
                  Waiting for source material
                </div>
              ) : null}
              {saveSuccessMessage !== null ? (
                <div className="mt-5 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
                  <CheckCircle2 className="h-4 w-4" />
                  {saveSuccessMessage}
                </div>
              ) : null}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
