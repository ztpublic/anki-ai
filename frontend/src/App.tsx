import React, { useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Library,
  Loader2,
  Settings,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import { motion } from "motion/react";

type Flashcard = {
  id: string;
  front: string;
  back: string;
};

const modelOptions = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "claude-3-opus", label: "Claude 3 Opus" },
  { value: "claude-3-sonnet", label: "Claude 3.5 Sonnet" },
  { value: "gemini-1.5-pro", label: "Gemini 1.5 Pro" },
];

function createCardId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function App() {
  const [llm, setLlm] = useState("gpt-4o");
  const [inputText, setInputText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [cardCount, setCardCount] = useState(5);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedCards, setGeneratedCards] = useState<Flashcard[]>([]);
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [savedLibrary, setSavedLibrary] = useState<Flashcard[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const currentCard = generatedCards[currentCardIndex];
  const canGenerate = inputText.trim().length > 0 || files.length > 0;

  const selectedModelLabel =
    modelOptions.find((option) => option.value === llm)?.label ?? llm;

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);

    if (selectedFiles.length > 0) {
      setFiles((previousFiles) => [...previousFiles, ...selectedFiles]);
      event.target.value = "";
    }
  };

  const removeFile = (indexToRemove: number) => {
    setFiles((previousFiles) =>
      previousFiles.filter((_, index) => index !== indexToRemove),
    );
  };

  const handleGenerate = async () => {
    if (!canGenerate || isGenerating) {
      return;
    }

    setIsGenerating(true);
    setGeneratedCards([]);
    setCurrentCardIndex(0);

    await new Promise((resolve) => {
      window.setTimeout(resolve, 2500);
    });

    const sourceType = files.length > 0 ? "files" : "text";
    const newCards: Flashcard[] = Array.from({ length: cardCount }, (_, index) => ({
      id: createCardId(),
      front: `Generated Question ${index + 1}\n\nWhat is the main concept derived from the provided ${sourceType}?`,
      back: `Generated Answer ${index + 1}\n\nThis is a simulated response based on the ${selectedModelLabel} model's analysis of your inputs.`,
    }));

    setGeneratedCards(newCards);
    setIsGenerating(false);
  };

  const handleDiscard = () => {
    setGeneratedCards((previousCards) =>
      previousCards.filter((_, index) => index !== currentCardIndex),
    );
    setCurrentCardIndex((previousIndex) =>
      Math.max(0, Math.min(previousIndex, generatedCards.length - 2)),
    );
  };

  const handleFinish = () => {
    setSavedLibrary((previousCards) => [...previousCards, ...generatedCards]);
    setGeneratedCards([]);
    setCurrentCardIndex(0);
  };

  const handleCardUpdate = (field: "front" | "back", value: string) => {
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
                htmlFor="model"
              >
                AI Model
              </label>
              <select
                id="model"
                value={llm}
                onChange={(event) => setLlm(event.target.value)}
                className="block h-8 w-full rounded-md border border-zinc-300 bg-white px-2 text-sm text-zinc-900 outline-none transition-all focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              >
                {modelOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
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
                  PDF, TXT, DOCX, MD (max 10MB)
                </span>
              </button>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                className="hidden"
                multiple
                accept=".pdf,.txt,.docx,.md"
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
                max="50"
                value={cardCount}
                onChange={(event) => setCardCount(Number(event.target.value))}
                className="h-2 w-full cursor-pointer appearance-none rounded bg-zinc-300 accent-indigo-600"
              />
            </div>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !canGenerate}
              className="mt-auto flex h-9 w-full items-center justify-center gap-2 rounded-md bg-indigo-600 px-3 text-sm font-semibold text-white transition-colors hover:bg-indigo-700 disabled:bg-zinc-300 disabled:text-zinc-500 disabled:hover:bg-zinc-300"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  Generate {cardCount} Cards
                </>
              )}
            </button>
          </div>
        </section>

        <section className="flex min-h-0 w-full flex-1 flex-col bg-zinc-50">
          {isGenerating ? (
            <div className="flex flex-1 flex-col items-center justify-center border-zinc-300 bg-zinc-50 p-8 text-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                className="relative mb-6"
              >
                <div className="h-16 w-16 rounded-full border-4 border-indigo-100 border-t-indigo-600" />
              </motion.div>
              <h3 className="mb-2 text-base font-semibold text-zinc-800">
                Analyzing your content...
              </h3>
              <p className="max-w-sm text-sm text-zinc-500">
                The {selectedModelLabel} model is reading through your content
                and identifying key concepts to create flashcards.
              </p>
            </div>
          ) : generatedCards.length > 0 && currentCard ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex h-11 shrink-0 items-center justify-between border-b border-zinc-300 bg-zinc-100 px-4">
                <h2 className="text-sm font-semibold text-zinc-800">
                  Review Cards
                </h2>
                <div className="text-xs font-medium text-zinc-500">
                  {currentCardIndex + 1} / {generatedCards.length}
                </div>
              </div>

              <motion.div
                key={currentCard.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.2 }}
                className="flex min-h-0 flex-1 flex-col overflow-hidden bg-white"
              >
                <div className="flex min-h-0 flex-1 flex-col border-b border-zinc-200 p-5">
                  <label
                    className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500"
                    htmlFor="card-front"
                  >
                    Front (Question)
                  </label>
                  <textarea
                    id="card-front"
                    value={currentCard.front}
                    onChange={(event) =>
                      handleCardUpdate("front", event.target.value)
                    }
                    className="min-h-0 w-full flex-1 resize-none rounded-md border border-transparent bg-transparent p-2 text-base text-zinc-800 outline-none placeholder:text-zinc-300 focus:border-indigo-200 focus:bg-indigo-50/20"
                    placeholder="Type the question here..."
                  />
                </div>
                <div className="flex min-h-0 flex-1 flex-col bg-zinc-50 p-5">
                  <label
                    className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500"
                    htmlFor="card-back"
                  >
                    Back (Answer)
                  </label>
                  <textarea
                    id="card-back"
                    value={currentCard.back}
                    onChange={(event) =>
                      handleCardUpdate("back", event.target.value)
                    }
                    className="min-h-0 w-full flex-1 resize-none rounded-md border border-transparent bg-transparent p-2 text-base text-zinc-800 outline-none placeholder:text-zinc-300 focus:border-indigo-200 focus:bg-white"
                    placeholder="Type the answer here..."
                  />
                </div>
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
                  className="flex h-8 items-center gap-2 rounded-md bg-zinc-800 px-3 text-sm font-medium text-white transition-colors hover:bg-zinc-700"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Save {generatedCards.length} Cards
                </button>
              </div>
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
                Provide source text or upload documents, adjust your settings,
                and generate a new deck of Anki flashcards.
              </p>
              {!canGenerate ? (
                <div className="mt-5 flex items-center gap-2 rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-xs font-medium text-zinc-500">
                  <AlertCircle className="h-4 w-4" />
                  Waiting for source material
                </div>
              ) : null}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
