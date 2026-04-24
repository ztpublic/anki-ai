Yes. For your case, use **assistant-ui as a read-only transcript renderer**, not as a chat runtime that sends user input.

The right shape is:

```txt
Claude Code SDK stream
        ↓
event adapter / normalizer
        ↓
your React state: AgentTraceMessage[]
        ↓
assistant-ui ExternalStoreRuntime
        ↓
custom ThreadPrimitive / MessagePrimitive renderer
```

assistant-ui’s **ExternalStoreRuntime** is the best fit because it lets you own the message state and convert your own message format into `ThreadMessageLike`; it is explicitly intended for custom state managers and custom message formats. ([assistant-ui][1]) Claude Code SDK streaming gives you incremental text via `content_block_delta` / `text_delta`, and tool calls via `content_block_start`, `content_block_delta` with `input_json_delta`, and `content_block_stop`, which maps cleanly into assistant-ui text parts and tool-call parts. ([Claude][2])

## 1. Install assistant-ui, but do not use the default full chat component as-is

For an existing project:

```bash
npx assistant-ui@latest init
```

or manually:

```bash
pnpm add @assistant-ui/react
```

The CLI is convenient, but the default `Thread` component is a normal chat interface and usually includes a composer. Your case is different: you want a **no-input, no-user-bubble, agent transcript view**. assistant-ui primitives are designed for this kind of custom layout; `ThreadPrimitive` handles the scrollable thread and message iteration, while you provide the layout. ([assistant-ui][3])

## 2. Create your own internal transcript model

Do not directly store Claude Code SDK events as UI messages. Normalize them first.

Example:

```ts
export type AgentTraceMessage =
  | {
      id: string;
      kind: "model_message";
      role: "assistant";
      text: string;
      status: "streaming" | "done" | "error";
      createdAt: number;
    }
  | {
      id: string;
      kind: "tool_call";
      toolCallId: string;
      toolName: string;
      argsText: string;
      args?: unknown;
      status: "streaming_args" | "running" | "done" | "error";
      result?: unknown;
      createdAt: number;
    }
  | {
      id: string;
      kind: "agent_event";
      title: string;
      body?: string;
      createdAt: number;
    };
```

For a code agent, I would keep **tool calls as first-class records**, not just text. That gives you expandable Bash cards, file-read cards, diff cards, permission cards, etc.

## 3. Build a Claude Code SDK event adapter

Your adapter should consume Claude Code SDK stream events and update the transcript store.

Pseudo-code:

```ts
function applyClaudeCodeEvent(
  event: any,
  store: AgentTraceStore,
) {
  const eventType = event.type;

  if (eventType === "content_block_start") {
    const block = event.content_block;

    if (block?.type === "tool_use") {
      store.addToolCall({
        toolCallId: block.id,
        toolName: block.name,
        argsText: "",
        status: "streaming_args",
      });
    }

    return;
  }

  if (eventType === "content_block_delta") {
    const delta = event.delta;

    if (delta?.type === "text_delta") {
      store.appendAssistantText(delta.text);
      return;
    }

    if (delta?.type === "input_json_delta") {
      store.appendToolArgs(delta.partial_json);
      return;
    }
  }

  if (eventType === "content_block_stop") {
    store.finishCurrentContentBlock();
    return;
  }
}
```

Claude’s streaming docs show exactly this split: text deltas are incremental `text_delta` chunks, while tool inputs stream through `input_json_delta`. ([Claude][2])

A practical implementation detail: for tool input JSON, keep both:

```ts
argsText: string; // raw streaming partial JSON
args?: unknown;  // parsed JSON only after it becomes valid
```

Do not assume every partial JSON chunk is parseable.

## 4. Convert your transcript model into assistant-ui messages

Use `useExternalStoreRuntime`.

assistant-ui’s docs show `convertMessage` returning `ThreadMessageLike`, with content like `{ type: "text", text: ... }`, and also show streaming by creating a placeholder assistant message and progressively updating its content. ([assistant-ui][1])

For your case:

```tsx
import {
  AssistantRuntimeProvider,
  ThreadMessageLike,
  useExternalStoreRuntime,
} from "@assistant-ui/react";

function convertTraceMessage(m: AgentTraceMessage): ThreadMessageLike {
  if (m.kind === "model_message") {
    return {
      id: m.id,
      role: "assistant",
      createdAt: new Date(m.createdAt),
      content: [
        {
          type: "text",
          text: m.text,
        },
      ],
    };
  }

  if (m.kind === "tool_call") {
    return {
      id: m.id,
      role: "assistant",
      createdAt: new Date(m.createdAt),
      content: [
        {
          type: "tool-call",
          toolCallId: m.toolCallId,
          toolName: m.toolName,
          args: m.args ?? { __rawPartialJson: m.argsText },
          result: m.result,
        } as any,
      ],
    };
  }

  return {
    id: m.id,
    role: "assistant",
    createdAt: new Date(m.createdAt),
    content: [
      {
        type: "text",
        text: `**${m.title}**\n\n${m.body ?? ""}`,
      },
    ],
  };
}

export function AgentTranscriptRuntimeProvider({
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

    // Not used because you will not render a composer.
    // Keep it defensive in case someone accidentally mounts one later.
    onNew: async () => {
      throw new Error("This transcript is read-only.");
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      {children}
    </AssistantRuntimeProvider>
  );
}
```

## 5. Build a custom transcript component with no composer

Use primitives, not the default chat component.

assistant-ui’s `ThreadPrimitive.Messages` accepts a render function where you can choose how each message role is rendered, and `MessagePrimitive.Parts` lets you customize text, image, tool-call, and other content parts. ([assistant-ui][3])

```tsx
import {
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";

export function AgentTranscript() {
  return (
    <ThreadPrimitive.Root className="flex h-full flex-col">
      <ThreadPrimitive.Viewport
        autoScroll
        turnAnchor="bottom"
        className="flex-1 overflow-y-auto p-3"
      >
        <ThreadPrimitive.Messages>
          {({ message }) => {
            // You can hide user-role messages entirely if your adapter emits them.
            if (message.role === "user") return null;

            return <AgentMessage />;
          }}
        </ThreadPrimitive.Messages>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

function AgentMessage() {
  return (
    <MessagePrimitive.Root className="mb-3">
      <div className="rounded-lg border bg-background p-3 text-sm">
        <MessagePrimitive.Parts>
          {({ part }) => {
            if (part.type === "text") {
              return <AgentTextPart />;
            }

            if (part.type === "tool-call") {
              return part.toolUI ?? <GenericToolCallPart part={part} />;
            }

            return null;
          }}
        </MessagePrimitive.Parts>
      </div>
    </MessagePrimitive.Root>
  );
}

function AgentTextPart() {
  return (
    <div className="prose prose-sm max-w-none">
      <MessagePartPrimitive.Text />
      <MessagePartPrimitive.InProgress>
        <span className="animate-pulse">▊</span>
      </MessagePartPrimitive.InProgress>
    </div>
  );
}

function GenericToolCallPart({ part }: { part: any }) {
  return (
    <details className="rounded-md border p-2">
      <summary className="cursor-pointer font-medium">
        Tool: {part.toolName}
      </summary>

      <pre className="mt-2 overflow-auto text-xs">
        {JSON.stringify(
          {
            args: part.args,
            result: part.result,
            status: part.status,
          },
          null,
          2,
        )}
      </pre>
    </details>
  );
}
```

Notice there is **no** `ComposerPrimitive.Root`, no input, and no send button.

## 6. Add custom UI for Claude Code tools

assistant-ui supports tool rendering. Its tools guide recommends registering tools through `Tools()` and supports backend tools whose execution happens elsewhere but still provide a render function. ([assistant-ui][4])

For Claude Code SDK, most tools are already executed by Claude Code, so treat them as **backend / UI-only tools**:

```tsx
import { AssistantRuntimeProvider, Tools, Toolkit, useAui } from "@assistant-ui/react";

const claudeCodeToolkit: Toolkit = {
  Bash: {
    type: "backend",
    render: ({ args, result }) => {
      return (
        <details className="rounded-md border p-2">
          <summary className="font-medium">Bash</summary>
          <pre className="mt-2 overflow-auto text-xs">
            {String((args as any)?.command ?? "")}
          </pre>
          {result ? (
            <pre className="mt-2 overflow-auto text-xs">
              {JSON.stringify(result, null, 2)}
            </pre>
          ) : null}
        </details>
      );
    },
  },

  Read: {
    type: "backend",
    render: ({ args, result }) => {
      return (
        <div className="rounded-md border p-2 text-sm">
          <div className="font-medium">Read file</div>
          <div className="text-muted-foreground">
            {(args as any)?.file_path}
          </div>
          {result ? (
            <pre className="mt-2 max-h-64 overflow-auto text-xs">
              {String(result)}
            </pre>
          ) : null}
        </div>
      );
    },
  },

  Edit: {
    type: "backend",
    render: ({ args, result }) => {
      return (
        <details className="rounded-md border p-2">
          <summary className="font-medium">Edit file</summary>
          <pre className="mt-2 overflow-auto text-xs">
            {JSON.stringify({ args, result }, null, 2)}
          </pre>
        </details>
      );
    },
  },
};
```

Then wire it into your provider:

```tsx
function AgentTranscriptProvider({
  runtime,
  children,
}: {
  runtime: any;
  children: React.ReactNode;
}) {
  const aui = useAui({
    tools: Tools({ toolkit: claudeCodeToolkit }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime} aui={aui}>
      {children}
    </AssistantRuntimeProvider>
  );
}
```

## 7. Decide what to do with “user” messages

Since you said **no user message box is needed**, I would avoid user-style bubbles entirely.

There are three reasonable options:

### Option A — hide user messages

Good if you only want model/tool trace.

```tsx
if (message.role === "user") return null;
```

### Option B — render user messages as collapsed agent prompts

Good if you want to debug the exact prompt sent from agent to LLM.

```tsx
if (message.role === "user") return <CollapsedAgentPrompt />;
```

Visually label it as:

```txt
Agent → LLM prompt
```

not as a human chat bubble.

### Option C — do not convert agent prompts into assistant-ui messages

Keep raw prompts in your own side panel or debug drawer. This is cleanest if the transcript should only show LLM-visible outputs and tool activity.

For code-agent debugging, I would choose **Option B during development** and **Option A in production**.

## 8. Recommended file structure

```txt
src/agent-ui/
  claude-code-event-adapter.ts
  agent-trace-types.ts
  agent-trace-store.ts
  convert-to-assistant-ui.ts
  AgentTranscriptRuntimeProvider.tsx
  AgentTranscript.tsx
  tool-ui/
    BashToolCard.tsx
    ReadToolCard.tsx
    EditToolCard.tsx
    GenericToolCard.tsx
```

## 9. Integration sequence

1. Add assistant-ui.
2. Implement `AgentTraceMessage`.
3. Implement the Claude Code SDK stream adapter.
4. Store normalized messages in React state, Zustand, Redux, or your existing session store.
5. Create `useExternalStoreRuntime`.
6. Render with `ThreadPrimitive`, not the stock `Thread`.
7. Omit `ComposerPrimitive`.
8. Hide or collapse role=`user` messages.
9. Add custom tool cards for `Bash`, `Read`, `Edit`, `Write`, `Grep`, etc.
10. Later add diff rendering, terminal ANSI rendering, and approval cards.

## My concrete recommendation

Start minimal:

```txt
Claude Code SDK events
→ AgentTraceMessage[]
→ useExternalStoreRuntime
→ ThreadPrimitive without ComposerPrimitive
→ MessagePrimitive.Parts with:
   - text renderer
   - generic tool-call renderer
```

Then specialize tool UIs one by one. For a code-agent UI, the first custom cards I would build are:

```txt
BashToolCard
ReadFileToolCard
EditFileToolCard
WriteFileToolCard
DiffToolCard
PermissionRequestCard
TodoPlanCard
```

This gives you a useful read-only agent transcript without fighting assistant-ui’s normal chat-input assumptions.

[1]: https://www.assistant-ui.com/docs/runtimes/custom/external-store "ExternalStoreRuntime | assistant-ui"
[2]: https://code.claude.com/docs/en/agent-sdk/streaming-output "Stream responses in real-time - Claude Code Docs"
[3]: https://www.assistant-ui.com/docs/primitives/thread "Thread | assistant-ui"
[4]: https://www.assistant-ui.com/docs/guides/tools "Tools | assistant-ui"
