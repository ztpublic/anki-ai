import React, { useRef, useState } from "react";
import {
  AlertCircle,
  BrainCircuit,
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
    <div className="h-full overflow-y-auto bg-slate-50 font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-indigo-600 p-1.5">
              <BrainCircuit className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">
              AnkiAI Creator
            </h1>
          </div>
          <div className="flex items-center gap-4 text-sm font-medium text-slate-600">
            <div className="flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1.5">
              <Library className="h-4 w-4" />
              <span>{savedLibrary.length} cards in library</span>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-8 sm:px-6 lg:flex-row">
        <section className="flex w-full flex-col gap-6 lg:w-1/3">
          <div className="flex flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Settings className="h-5 w-5 text-slate-500" />
              Generator Settings
            </h2>

            <div className="space-y-1.5">
              <label
                className="block text-sm font-medium text-slate-700"
                htmlFor="model"
              >
                AI Model
              </label>
              <select
                id="model"
                value={llm}
                onChange={(event) => setLlm(event.target.value)}
                className="block w-full rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-sm text-slate-900 outline-none transition-all focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
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
                className="block text-sm font-medium text-slate-700"
                htmlFor="source-text"
              >
                Source Text
              </label>
              <textarea
                id="source-text"
                value={inputText}
                onChange={(event) => setInputText(event.target.value)}
                placeholder="Paste the text you want to convert into flashcards..."
                className="block h-32 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-700">
                Additional Files
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="group flex w-full flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 p-4 text-center transition-all hover:border-indigo-300 hover:bg-slate-50"
              >
                <UploadCloud className="mb-2 h-6 w-6 text-slate-400 transition-colors group-hover:text-indigo-500" />
                <span className="text-sm font-medium text-slate-600">
                  Click to upload documents
                </span>
                <span className="mt-1 text-xs text-slate-400">
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
                      className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 p-2 pl-3 text-sm"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                        <span className="truncate text-slate-700">
                          {file.name}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeFile(index)}
                        className="rounded-md p-1 text-slate-500 transition-colors hover:bg-slate-200"
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
                className="flex justify-between text-sm font-medium text-slate-700"
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
                className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
              />
            </div>

            <button
              type="button"
              onClick={handleGenerate}
              disabled={isGenerating || !canGenerate}
              className="mt-2 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 font-medium text-white transition-all hover:bg-indigo-700 active:scale-[0.98] disabled:bg-slate-300 disabled:hover:bg-slate-300"
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

        <section className="flex min-h-[500px] w-full flex-col lg:w-2/3">
          {isGenerating ? (
            <div className="flex flex-1 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center shadow-sm">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
                className="relative mb-6"
              >
                <div className="h-16 w-16 rounded-full border-4 border-indigo-100 border-t-indigo-600" />
              </motion.div>
              <h3 className="mb-2 text-lg font-semibold text-slate-800">
                Analyzing your content...
              </h3>
              <p className="max-w-sm text-sm text-slate-500">
                The {selectedModelLabel} model is reading through your content
                and identifying key concepts to create flashcards.
              </p>
            </div>
          ) : generatedCards.length > 0 && currentCard ? (
            <div className="flex flex-1 flex-col">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-xl font-bold text-slate-800">
                  Review Cards
                </h2>
                <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 shadow-sm">
                  {currentCardIndex + 1} / {generatedCards.length}
                </div>
              </div>

              <motion.div
                key={currentCard.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.2 }}
                className="flex flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
              >
                <div className="flex flex-1 flex-col border-b border-slate-100 p-6">
                  <label
                    className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400"
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
                    className="h-48 w-full flex-1 resize-none bg-transparent text-lg text-slate-800 outline-none placeholder:text-slate-300"
                    placeholder="Type the question here..."
                  />
                </div>
                <div className="flex flex-1 flex-col bg-slate-50 p-6">
                  <label
                    className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400"
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
                    className="h-48 w-full flex-1 resize-none bg-transparent text-lg text-slate-800 outline-none placeholder:text-slate-300"
                    placeholder="Type the answer here..."
                  />
                </div>
              </motion.div>

              <div className="mt-6 flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <button
                  type="button"
                  onClick={handleDiscard}
                  className="flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium text-rose-600 transition-colors hover:bg-rose-50"
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
                    className="rounded-xl border border-slate-200 p-2 text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
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
                    className="rounded-xl border border-slate-200 p-2 text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                    aria-label="Next card"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleFinish}
                  className="flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Save {generatedCards.length} Cards
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center shadow-sm">
              <div className="mb-4 rounded-full bg-slate-100 p-4">
                <Library className="h-8 w-8 text-slate-400" />
              </div>
              <h3 className="mb-2 text-lg font-semibold text-slate-800">
                Ready to generate
              </h3>
              <p className="max-w-sm text-sm text-slate-500">
                Provide source text or upload documents, adjust your settings,
                and generate a new deck of Anki flashcards.
              </p>
              {!canGenerate ? (
                <div className="mt-5 flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-500">
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
